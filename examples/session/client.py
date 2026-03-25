#!/usr/bin/env python3
"""
Demo client for Vast.ai serverless PyTorch training endpoints.

Usage:
    python client.py --endpoint my-pytorch-endpoint --sessions 3 --epochs 5
"""

import argparse
import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

import vastai


@dataclass
class SessionResult:
    session_id: str
    success: bool
    start_time: float
    end_time: float
    final_status: Optional[dict] = None
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


async def close_sessions(sessions: list[Any]) -> None:
    """Close all open sessions."""
    for session in sessions:
        try:
            if await session.is_open():
                print(f"  Closing session {session.session_id[:8]}...")
                await session.close()
        except Exception as e:
            print(f"  Failed to close {session.session_id[:8]}: {e}")


async def run_training_session(
    endpoint,
    session: Any,
    epochs: int,
    max_train_batches: int,
    poll_interval: float = 1.0,
    debug: bool = False,
) -> SessionResult:
    """
    Run a training session: start the task, poll for status, return results.
    """
    session_id = session.session_id
    start_time = time.time()

    payload = {
        "epochs": epochs,
        "max_train_batches_per_epoch": max_train_batches,
        "session_id": session_id,
    }

    # Start the task and check the initial response
    try:
        resp = await session.request(route="/start_task", payload=payload)
        if debug:
            print(f"  [{session_id[:8]}] /start_task response: {resp}")

        # SDK wraps the model response in a "response" key
        inner = resp.get("response", resp)
        status = inner.get("status", {})
        state = status.get("state", "unknown")
        print(f"  [{session_id[:8]}] Task started, initial state={state}")

        # If task already completed in the start call
        if state in ("completed", "failed", "canceled"):
            return SessionResult(
                session_id=session_id,
                success=(state == "completed"),
                start_time=start_time,
                end_time=time.time(),
                final_status=status,
                error=status.get("error") if state == "failed" else None,
            )
    except Exception as e:
        return SessionResult(
            session_id=session_id,
            success=False,
            start_time=start_time,
            end_time=time.time(),
            error=f"Failed to start task: {e}",
        )

    final_status = status
    last_state = state

    # Poll until completion or session closes
    while await session.is_open():
        await asyncio.sleep(poll_interval)
        try:
            resp = await session.request(route="/status", payload={}, retry=False)
            if debug:
                print(f"  [{session_id[:8]}] /status response: {resp}")

            inner = resp.get("response", resp)
            status = inner.get("status", {})
            state = status.get("state", "unknown")
            epoch = status.get("epoch", 0)
            step = status.get("step", 0)
            total = status.get("total_steps", 0)
            msg = status.get("message", "")

            print(f"  [{session_id[:8]}] state={state} epoch={epoch} step={step}/{total} - {msg}")

            final_status = status
            last_state = state

            if state in ("completed", "failed", "canceled"):
                break

        except Exception:
            print(f"  [{session_id[:8]}] Session closed (training likely completed)")
            break

    success = last_state in ("completed", "running")
    error = None
    if final_status and final_status.get("state") == "failed":
        success = False
        error = final_status.get("error", "Unknown error")

    return SessionResult(
        session_id=session_id,
        success=success,
        start_time=start_time,
        end_time=time.time(),
        final_status=final_status,
        error=error,
    )


def print_summary(results: list[SessionResult]) -> None:
    """Print a summary of all training session results."""
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print(f"Total sessions: {len(results)}")
    print(f"Successful:     {len(successful)}")
    print(f"Failed:         {len(failed)}")

    if successful:
        durations = [r.duration for r in successful]
        print(f"\nSuccessful session durations:")
        print(f"  Min:  {min(durations):.2f}s")
        print(f"  Max:  {max(durations):.2f}s")
        print(f"  Avg:  {sum(durations) / len(durations):.2f}s")

    if failed:
        print(f"\nFailed sessions:")
        for r in failed:
            print(f"  [{r.session_id[:8]}] {r.error}")

    print("\nPer-session details:")
    for r in results:
        status_str = "OK" if r.success else "FAILED"
        print(f"  [{r.session_id[:8]}] {status_str} - {r.duration:.2f}s")
        if r.final_status:
            val_acc = r.final_status.get("val_acc")
            val_loss = r.final_status.get("val_loss")
            train_acc = r.final_status.get("train_acc")
            if val_acc is not None:
                print(f"    Final val_acc:  {val_acc:.4f}")
            if val_loss is not None:
                print(f"    Final val_loss: {val_loss:.4f}")
            if train_acc is not None:
                print(f"    Final train_acc: {train_acc:.4f}")

    print("=" * 60)


async def main(
    endpoint_name: str,
    num_sessions: int,
    epochs: int,
    max_train_batches: int,
    session_cost: float,
    debug: bool = False,
) -> None:
    print(f"Starting {num_sessions} training session(s) on endpoint '{endpoint_name}'")
    print(f"Config: epochs={epochs}, max_train_batches={max_train_batches}")
    print()

    sessions = []
    results = []

    async with vastai.Serverless(max_poll_interval=0.1) as client:
        endpoint = await client.get_endpoint(endpoint_name)

        try:
            # Step 1: Create all sessions
            print("Creating sessions...")
            for i in range(num_sessions):
                session = await endpoint.session(cost=session_cost, on_close_route="/cancel_task")
                sessions.append(session)
                print(f"  Created session {i+1}/{num_sessions}: {session.session_id[:8]}")

            print(f"\nCreated {len(sessions)} session(s)\n")

            # Step 2: Run training on all sessions concurrently
            print("Starting training runs...")
            training_tasks = [
                run_training_session(
                    endpoint=endpoint,
                    session=s,
                    epochs=epochs,
                    max_train_batches=max_train_batches,
                    debug=debug,
                )
                for s in sessions
            ]

            results = await asyncio.gather(*training_tasks, return_exceptions=True)
            results = [r for r in results if isinstance(r, SessionResult)]

        except KeyboardInterrupt:
            print("\n\nInterrupted.")
        finally:
            print("\nCleaning up sessions...")
            await close_sessions(sessions)

    if results:
        print_summary(results)
    else:
        print("\nNo results to report.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo client for Vast.ai serverless training")
    parser.add_argument("--endpoint", type=str, required=True, help="Name of the serverless endpoint")
    parser.add_argument("--sessions", type=int, default=3, help="Number of concurrent sessions")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--max-train-batches", type=int, default=10, help="Max batches per epoch")
    parser.add_argument("--session-cost", type=float, default=10.0, help="Cost budget per session")
    parser.add_argument("--debug", action="store_true", help="Print raw API responses")

    args = parser.parse_args()

    asyncio.run(
        main(
            endpoint_name=args.endpoint,
            num_sessions=args.sessions,
            epochs=args.epochs,
            max_train_batches=args.max_train_batches,
            session_cost=args.session_cost,
            debug=args.debug,
        )
    )