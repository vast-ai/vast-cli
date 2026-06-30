"""Tests for ``vastai run benchmarks``.

Covers the two things that actually matter:
  1. Cleanup invariant — the workergroup and endpoint are deleted on every
     exit path (success, timeout, exception, Ctrl-C).
  2. Happy-path shape — the command provisions, polls, extracts
     measured_perf, and returns rows.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from vastai.cli.commands import benchmarks as bench


# ---------------------------------------------------------------------------
# benchmark_gpu — cleanup invariant
# ---------------------------------------------------------------------------


def _mk_vast(*, create_endpoint=None, create_workergroup=None,
             get_endpoint_workers=None, delete_workergroup=None,
             delete_endpoint=None, show_instance=None,
             create_workergroup_raises=None, delete_workergroup_raises=None):
    """Build a MagicMock VastAI with serverless methods configured."""
    v = MagicMock()
    v.client = MagicMock()
    v.client.api_key = "k"
    v.create_endpoint.return_value = (create_endpoint
                                      if create_endpoint is not None
                                      else {"success": True, "result": 11})
    if create_workergroup_raises:
        v.create_workergroup.side_effect = create_workergroup_raises
    else:
        v.create_workergroup.return_value = (create_workergroup
                                             if create_workergroup is not None
                                             else {"success": True, "result": 999})
    if isinstance(get_endpoint_workers, list):
        v.get_endpoint_workers.side_effect = get_endpoint_workers
    elif get_endpoint_workers is not None:
        v.get_endpoint_workers.return_value = get_endpoint_workers
    else:
        v.get_endpoint_workers.return_value = []
    if delete_workergroup_raises:
        v.delete_workergroup.side_effect = delete_workergroup_raises
    else:
        v.delete_workergroup.return_value = (delete_workergroup
                                             if delete_workergroup is not None
                                             else {"success": True})
    v.delete_endpoint.return_value = (delete_endpoint
                                      if delete_endpoint is not None
                                      else {"success": True})
    v.show_instance.return_value = (show_instance
                                    if show_instance is not None
                                    else {"dph_total": 0.5})
    return v


class TestBenchmarkOne:
    def test_happy_path_returns_ok(self):
        vast = _mk_vast(get_endpoint_workers=[
            [{"id": 1, "measured_perf": 42.0, "status": "idle"}],
        ])
        with patch.object(bench.time, "sleep", return_value=None), \
             patch.object(bench.time, "monotonic",
                          side_effect=[0, 0, 1, 2, 3, 4, 5, 6]):
            active_wgs = set()
            active_eps = set()
            gpu, num_gpus, status, perf, err, price = bench.benchmark_gpu(
                vast,
                gpu_name="RTX 4080", num_gpus=1, timeout=60,
                workergroups=active_wgs, endpoints=active_eps,
                template_id=99999,
            )
            assert status == "ok"
            assert perf == 42.0
            assert err is None
            vast.delete_workergroup.assert_called_once_with(id=999)
            assert active_wgs == set()
            assert active_eps == set()
            call = vast.create_workergroup.call_args
            assert call.kwargs["template_id"] == 99999
            assert "gpu_name=RTX_4080" in call.kwargs["search_params"]
            assert "num_gpus=1" in call.kwargs["search_params"]
            assert "verified" not in call.kwargs["search_params"]

    def test_template_id_wins_over_hash(self):
        vast = _mk_vast(get_endpoint_workers=[
            [{"id": 1, "measured_perf": 1.0, "status": "idle"}],
        ])
        with patch.object(bench.time, "sleep", return_value=None), \
             patch.object(bench.time, "monotonic",
                          side_effect=[0, 0, 1, 2, 3, 4, 5, 6]):
            bench.benchmark_gpu(
                vast,
                gpu_name="RTX 3060", num_gpus=1, timeout=60,
                workergroups=set(), endpoints=set(),
                template_id=12345, template_hash="abc",
            )
            call = vast.create_workergroup.call_args
            assert call.kwargs.get("template_id") == 12345
            # When --template_id is provided, hash must NOT be passed (id is the canonical key).
            assert "template_hash" not in call.kwargs

    def test_template_hash_used_when_no_id(self):
        vast = _mk_vast(get_endpoint_workers=[
            [{"id": 1, "measured_perf": 1.0, "status": "idle"}],
        ])
        with patch.object(bench.time, "sleep", return_value=None), \
             patch.object(bench.time, "monotonic",
                          side_effect=[0, 0, 1, 2, 3, 4, 5, 6]):
            bench.benchmark_gpu(
                vast,
                gpu_name="RTX 3060", num_gpus=1, timeout=60,
                workergroups=set(), endpoints=set(),
                template_hash="abc123",
            )
            call = vast.create_workergroup.call_args
            assert call.kwargs.get("template_hash") == "abc123"
            assert "template_id" not in call.kwargs

    def test_timeout_still_tears_down(self):
        vast = _mk_vast(create_workergroup={"success": True, "result": 777},
                        get_endpoint_workers=[[]])
        with patch.object(bench.time, "sleep"), \
             patch.object(bench.time, "monotonic",
                          side_effect=[0, 0, 2, 3, 4, 5]):
            active_wgs = set()
            active_eps = set()
            gpu, num_gpus, status, perf, err, price = bench.benchmark_gpu(
                vast,
                gpu_name="RTX 3060", num_gpus=1, timeout=1,
                workergroups=active_wgs,
                endpoints=active_eps,
            )
            assert status == "timeout"
            assert perf is None
            vast.delete_workergroup.assert_called_once()
            assert active_wgs == set()
            assert active_eps == set()

    def test_create_failure_records_error_and_no_teardown(self):
        # create_endpoint succeeds, but create_workergroup raises. The
        # workergroup never came into existence (no delete_workergroup),
        # but the endpoint did and must be torn down by finally.
        vast = _mk_vast(create_workergroup_raises=RuntimeError("boom"))
        with patch.object(bench.time, "monotonic", return_value=0):
            active_wgs = set()
            active_eps = set()
            with pytest.raises(RuntimeError):
                bench.benchmark_gpu(
                    vast,
                    gpu_name="RTX 3060", num_gpus=1, timeout=10,
                    workergroups=active_wgs,
                    endpoints=active_eps,
                )
            vast.delete_workergroup.assert_not_called()
            vast.delete_endpoint.assert_called_once()
            assert active_wgs == set()
            assert active_eps == set()

    def test_create_returns_no_id_reports_error(self):
        vast = _mk_vast(create_workergroup={"success": False})
        with patch.object(bench.time, "monotonic", return_value=0):
            gpu, num_gpus, status, perf, err, price = bench.benchmark_gpu(
                vast,
                gpu_name="RTX 3060", num_gpus=1, timeout=10,
                workergroups=set(), endpoints=set(),
            )
            assert status == "error"
            assert "no id" in err
            vast.delete_workergroup.assert_not_called()

    def test_all_workers_terminal_bails_fast(self):
        # All workers in a terminal state (stopped) for >_TERMINAL_DEBOUNCE
        # without producing measured_perf -> fail fast. ``error`` is no longer
        # treated as terminal because the autoscaler restarts errored workers
        # via error -> rebooting -> model_loading.
        poll = [{"id": 1, "status": "stopped"}]
        vast = _mk_vast(create_workergroup={"success": True, "result": 1},
                        get_endpoint_workers=[poll, poll])
        with patch.object(bench.time, "sleep"), \
             patch.object(bench.time, "monotonic",
                          side_effect=[0, 0, 0, 5, 5, 50, 50]):
            gpu, num_gpus, status, perf, err, price = bench.benchmark_gpu(
                vast,
                gpu_name="RTX 3060", num_gpus=1, timeout=600,
                workergroups=set(), endpoints=set(),
            )
            assert status == "failed"
            assert "terminal" in err
            vast.delete_workergroup.assert_called_once()

    def test_delete_failure_does_not_raise(self):
        # delete_workergroup raises in finally; should be caught and logged.
        poll = [{"id": 1, "measured_perf": 5.0, "status": "idle"}]
        vast = _mk_vast(create_workergroup={"success": True, "result": 1},
                        get_endpoint_workers=[poll],
                        delete_workergroup_raises=RuntimeError("delete failed"),
                        show_instance={"dph_total": 1.0})
        with patch.object(bench.time, "sleep"), \
             patch.object(bench.time, "monotonic", side_effect=[0, 0, 1]):
            gpu, num_gpus, status, perf, err, price = bench.benchmark_gpu(
                vast,
                gpu_name="RTX 3060", num_gpus=1, timeout=60,
                workergroups=set(), endpoints=set(),
            )
            assert status == "ok"


# ---------------------------------------------------------------------------
# CLI integration: args.func(args) with a patched VastAI class
# ---------------------------------------------------------------------------


_FAKE_TEMPLATE = {"id": 99999, "hash_id": "x", "extra_filters": "{}"}


def _run_cli(parse_argv, argv, *, create_resp=None, workers_seq=None,
             rental_dph=None, template=None, preflight_offers=1,
             create_workergroup_raises=None, benchmark_rows=None,
             input_side_effect=None):
    """Parse argv and invoke the command with a mocked VastAI."""
    template = template if template is not None else _FAKE_TEMPLATE
    fake_offer_list = [{"id": i} for i in range(preflight_offers)]
    instance_resp = {"dph_total": rental_dph} if rental_dph is not None else {}

    vast = MagicMock()
    vast.client = MagicMock(api_key="k")
    vast.search_templates.return_value = [template]
    vast.search_offers.return_value = fake_offer_list
    vast.search_benchmarks.return_value = list(benchmark_rows or [])
    vast.show_instance.return_value = instance_resp
    vast.create_endpoint.return_value = {"success": True, "result": 11}
    vast.delete_endpoint.return_value = {}
    if create_workergroup_raises:
        vast.create_workergroup.side_effect = create_workergroup_raises
    else:
        vast.create_workergroup.return_value = (create_resp
                                                if create_resp is not None
                                                else {"success": True, "result": 500})
    vast.get_endpoint_workers.side_effect = list(workers_seq or [[]])
    vast.delete_workergroup.return_value = {}

    ctx = [patch.object(bench, "VastAI", return_value=vast),
           patch.object(bench.time, "sleep")]
    if input_side_effect is not None:
        ctx.append(patch("builtins.input", side_effect=input_side_effect))
    with ExitStack() as stack:
        for c in ctx:
            stack.enter_context(c)
        args = parse_argv(argv)
        return args.func(args), vast


class TestBenchmarkRunCLI:
    def test_happy_path_returns_rows(self, parse_argv):
        result, _ = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_4080", "--timeout", "60", "-y", "--raw"],
            workers_seq=[[{"id": 1, "measured_perf": 100.0, "status": "idle"}]],
            rental_dph=0.5,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        row = result[0]
        assert row["gpu_name"] == "RTX 4080"
        assert row["measured_perf"] == 100.0
        assert row["status"] == "ok"
        assert row["rental_dph"] == 0.5
        assert row["perf_per_dollar"] == 200.0

    def test_missing_template_flag_errors(self, parse_argv, capsys):
        args = parse_argv([
            "run", "benchmarks", "--gpus", "RTX_3060",
            "--timeout", "60", "-y", "--raw",
        ])
        rc = args.func(args)
        assert rc == 1
        assert "template_id" in capsys.readouterr().err

    def test_endpoint_name_includes_gpu_spec(self, parse_argv):
        _, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw"],
            create_resp={"result": 2},
            workers_seq=[[{"id": 1, "measured_perf": 1.0, "status": "idle"}]],
            rental_dph=0.5,
        )
        name = vast.create_endpoint.call_args.kwargs["endpoint_name"]
        assert name.startswith("benchmark 1x RTX 3060 ")
        # Backend rejects shell chars in endpoint_name (e.g. parens), so the
        # uniqueness suffix must avoid them.
        assert not set(name) & set(";&|(){}$`<>*?[]")

    def test_endpoint_deleted_even_on_exception(self, parse_argv):
        rows, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw"],
            create_workergroup_raises=RuntimeError("boom"),
        )
        assert rows[0]["status"] == "error"
        vast.delete_endpoint.assert_called()

    def test_template_id_threaded_to_workergroup(self, parse_argv):
        _, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "12345",
             "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw"],
            create_resp={"result": 2},
            workers_seq=[[{"id": 7, "measured_perf": 1, "status": "idle"}]],
            rental_dph=0.5,
        )
        assert vast.create_workergroup.call_args.kwargs["template_id"] == 12345

    def test_no_offers_skips_class(self, parse_argv):
        # Pre-flight returns 0 offers — class should be skipped without ever
        # creating a workergroup.
        rows, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw"],
            preflight_offers=0,
        )
        assert rows[0]["status"] == "skipped"
        vast.create_workergroup.assert_not_called()

    def test_template_not_found_errors(self, parse_argv, capsys):
        vast = MagicMock()
        vast.search_templates.return_value = []
        with patch.object(bench, "VastAI", return_value=vast):
            args = parse_argv([
                "run", "benchmarks", "--template_id", "99999",
                "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
            ])
            rc = args.func(args)
            assert rc == 1
            assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Cached-benchmark pre-flight
# ---------------------------------------------------------------------------


def _bench_row(value, *, template_hash="x", template_id=None, age_days=1):
    import time
    return {"type": "perf", "gpu_name": "RTX 3060", "num_gpus": 1,
            "template_hash": template_hash, "template_id": template_id,
            "value": value, "last_update": time.time() - age_days * 86400}


class TestBenchmarkCache:
    def test_cache_hit_skips_rental_and_uses_median(self, parse_argv):
        rows, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "-y", "--raw"],
            benchmark_rows=[_bench_row(10.0), _bench_row(30.0),
                            _bench_row(20.0)],
        )
        assert rows[0]["status"] == "cached"
        assert rows[0]["measured_perf"] == 20.0
        vast.create_endpoint.assert_not_called()
        vast.create_workergroup.assert_not_called()

    def test_cached_rows_have_no_price(self, parse_argv):
        # Cached rows report perf only; $/hr would come from a different
        # machine than the one benchmarked, so it is omitted.
        rows, _ = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "-y", "--raw"],
            benchmark_rows=[_bench_row(20.0)],
        )
        assert rows[0]["rental_dph"] is None
        assert rows[0]["perf_per_dollar"] is None

    def test_cached_unrentable_is_flagged(self, parse_argv, capsys):
        rows, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "-y", "--raw"],
            benchmark_rows=[_bench_row(10.0)],
            preflight_offers=0,
        )
        assert rows[0]["status"] == "cached"
        assert rows[0]["measured_perf"] == 10.0
        vast.create_endpoint.assert_not_called()
        err = " ".join(capsys.readouterr().err.split())  # rich may wrap lines
        assert "no offers available to rent" in err.lower()

    def test_cache_hit_interactive_decline_uses_cache(self, parse_argv, capsys):
        # No -y/--raw: user is prompted and declines (empty input) -> keep cached, no rental.
        _, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60"],
            benchmark_rows=[_bench_row(20.0)],
            input_side_effect=[""],
        )
        vast.create_endpoint.assert_not_called()
        out = capsys.readouterr()
        assert "cached" in (out.out + out.err)

    def test_cache_hit_interactive_accept_runs_fresh(self, parse_argv):
        # User opts into a fresh run ('y'), then confirms the rental ('y').
        _, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60"],
            benchmark_rows=[_bench_row(20.0)],
            workers_seq=[[{"id": 1, "measured_perf": 5.0, "status": "idle"}]],
            rental_dph=0.5,
            input_side_effect=["y", "y"],
        )
        vast.create_endpoint.assert_called()
        vast.create_workergroup.assert_called_once()

    def test_no_cache_bypasses_cache(self, parse_argv):
        rows, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
             "--no-cache"],
            benchmark_rows=[_bench_row(10.0)],
            workers_seq=[[{"id": 1, "measured_perf": 5.0, "status": "idle"}]],
            rental_dph=0.5,
        )
        vast.search_benchmarks.assert_not_called()
        assert rows[0]["status"] == "ok"
        assert rows[0]["measured_perf"] == 5.0

    def test_other_template_rows_are_a_miss(self, parse_argv):
        rows, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw"],
            benchmark_rows=[_bench_row(10.0, template_hash="other")],
            workers_seq=[[{"id": 1, "measured_perf": 5.0, "status": "idle"}]],
            rental_dph=0.5,
        )
        assert rows[0]["status"] == "ok"
        vast.create_workergroup.assert_called_once()

    def test_row_matching_by_template_id_only(self, parse_argv):
        # Autoscaler rows may carry only template_id (no hash) depending on
        # how the workergroup was created.
        rows, _ = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "-y", "--raw"],
            benchmark_rows=[_bench_row(7.0, template_hash=None,
                                       template_id=99999)],
        )
        assert rows[0]["status"] == "cached"
        assert rows[0]["measured_perf"] == 7.0

    def test_cache_query_shape(self, parse_argv):
        import time
        from vastai.cli.commands.benchmarks import DEFAULT_CACHE_MAX_AGE_DAYS
        _, vast = _run_cli(
            parse_argv,
            ["run", "benchmarks", "--template_id", "99999",
             "--gpus", "RTX_3060", "-y", "--raw"],
            benchmark_rows=[_bench_row(20.0)],
        )
        query = vast.search_benchmarks.call_args.kwargs["query"]
        assert query["type"] == {"eq": "perf"}
        assert query["gpu_name"] == {"eq": "RTX 3060"}
        assert query["num_gpus"] == {"eq": 1}
        cutoff = query["last_update"]["gte"]
        assert abs((time.time() - cutoff)
                   - DEFAULT_CACHE_MAX_AGE_DAYS * 86400) < 60

