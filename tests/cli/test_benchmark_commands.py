"""Tests for ``vastai benchmark run``.

Covers the two things that actually matter:
  1. Cleanup invariant — the workergroup and endpoint are deleted on every
     exit path (success, timeout, exception, Ctrl-C).
  2. Happy-path shape — the command provisions, polls, extracts
     measured_perf, and returns rows.
"""

from unittest.mock import MagicMock, patch

import pytest

from vastai.cli.commands import benchmark as bench


# ---------------------------------------------------------------------------
# Pure-function helpers (no CLI boot required)
# ---------------------------------------------------------------------------


class TestExtractId:
    def test_result_key(self):
        assert bench._extract_id({"success": True, "result": 42}, "result", "id") == 42

    def test_nested_results_dict(self):
        assert bench._extract_id({"results": {"endpoint_id": 7}},
                                 "result", "endpoint_id", "id") == 7

    def test_none_on_missing(self):
        assert bench._extract_id({}, "result") is None

    def test_none_on_non_int(self):
        assert bench._extract_id({"result": "oops"}, "result") is None


class TestNormalizeWorkers:
    def test_bare_list(self):
        assert bench._normalize_workers([{"id": 1}]) == [{"id": 1}]

    def test_wrapped_dict(self):
        assert bench._normalize_workers({"workers": [{"id": 2}]}) == [{"id": 2}]

    def test_error_shape(self):
        assert bench._normalize_workers({"error_msg": "x"}) == []


# ---------------------------------------------------------------------------
# _benchmark_one — cleanup invariant
# ---------------------------------------------------------------------------


def _mk_client():
    c = MagicMock()
    c.api_key = "k"
    c.server_url = "https://console.vast.ai"
    return c


def _patch_api(create_resp=None, workers_responses=None, delete_raises=None,
               create_raises=None, instance_dph=0.5):
    """Return an ExitStack-ready tuple of patches for the API helpers.

    ``_benchmark_one`` calls ``get_endpoint_workers`` once *before* the
    workergroup is created (to snapshot pre-existing worker ids) and then
    once per poll. We transparently prepend an empty snapshot to the
    workers_responses sequence so callers don't have to think about it.

    On the success path it also calls ``show_instance(worker_id)`` to grab
    the actual dph_total. We mock that with ``instance_dph``.
    """
    create_resp = create_resp if create_resp is not None else {
        "success": True, "result": 999,
    }
    workers_seq = [[]] + list(workers_responses or [[]])
    patches = [
        patch.object(bench.endpoints_api, "create_workergroup",
                     side_effect=create_raises,
                     return_value=None if create_raises else create_resp),
        patch.object(bench.endpoints_api, "get_endpoint_workers",
                     side_effect=workers_seq),
        patch.object(bench.endpoints_api, "delete_workergroup",
                     side_effect=delete_raises,
                     return_value={"success": True}),
        patch.object(bench.instances_api, "show_instance",
                     return_value={"dph_total": instance_dph}),
        patch.object(bench.time, "sleep", return_value=None),
        patch.object(bench.time, "monotonic", side_effect=[0, 0, 1, 2, 3, 4, 5, 6]),
    ]
    return patches


class TestBenchmarkOne:
    def test_happy_path_returns_ok(self):
        patches = _patch_api(
            workers_responses=[
                [{"id": 1, "measured_perf": 42.0, "status": "idle"}],
            ],
        )
        with patches[0] as mc, patches[1], patches[2] as md, patches[3], patches[4], patches[5]:
            active = set()
            gpu, status, perf, err, price = bench._benchmark_one(
                _mk_client(),
                endpoint_id=5, endpoint_name="benchmark-abc",
                gpu_class="RTX 4080", num_gpus=1, timeout=60, active=active,
                template_id=99999,
            )
            assert status == "ok"
            assert perf == 42.0
            assert err is None
            # Teardown ran on success
            md.assert_called_once_with(pytest.importorskip("unittest").mock.ANY,
                                       id=999)
            # Active set drained
            assert active == set()
            # Search params contain gpu_name and num_gpus (and NOT verified=)
            call = mc.call_args
            assert call.kwargs["template_id"] == 99999
            assert "gpu_name=RTX_4080" in call.kwargs["search_params"]
            assert "num_gpus=1" in call.kwargs["search_params"]
            assert "verified" not in call.kwargs["search_params"]
            assert "geolocation=US" in call.kwargs["search_params"]

    def test_template_id_wins_over_hash(self):
        patches = _patch_api(
            workers_responses=[
                [{"id": 1, "measured_perf": 1.0, "status": "idle"}],
            ],
        )
        with patches[0] as mc, patches[1], patches[2], patches[3], patches[4], patches[5]:
            bench._benchmark_one(
                _mk_client(),
                endpoint_id=5, endpoint_name="ep",
                gpu_class="RTX 3060", num_gpus=1, timeout=60, active=set(),
                template_id=12345, template_hash="abc",
            )
            call = mc.call_args
            assert call.kwargs.get("template_id") == 12345
            # When --template-id is provided, hash must NOT be passed (avoids
            # the hash-resolution bug from serverless-bugs.md #6).
            assert "template_hash" not in call.kwargs

    def test_template_hash_used_when_no_id(self):
        patches = _patch_api(
            workers_responses=[
                [{"id": 1, "measured_perf": 1.0, "status": "idle"}],
            ],
        )
        with patches[0] as mc, patches[1], patches[2], patches[3], patches[4], patches[5]:
            bench._benchmark_one(
                _mk_client(),
                endpoint_id=5, endpoint_name="ep",
                gpu_class="RTX 3060", num_gpus=1, timeout=60, active=set(),
                template_hash="abc123",
            )
            call = mc.call_args
            assert call.kwargs.get("template_hash") == "abc123"
            assert "template_id" not in call.kwargs

    def test_timeout_still_tears_down(self):
        # monotonic yields 0 (start), then values that exceed timeout=1.
        with patch.object(bench.endpoints_api, "create_workergroup",
                          return_value={"success": True, "result": 777}):
            with patch.object(bench.endpoints_api, "get_endpoint_workers",
                              return_value=[]):
                with patch.object(bench.endpoints_api, "delete_workergroup",
                                  return_value={}) as md:
                    with patch.object(bench.time, "sleep"):
                        with patch.object(bench.time, "monotonic",
                                          side_effect=[0, 0, 2, 3, 4, 5]):
                            active = set()
                            gpu, status, perf, err, price = bench._benchmark_one(
                                _mk_client(),
                                endpoint_id=1, endpoint_name="ep",
                                gpu_class="RTX 3060", num_gpus=1,
                                timeout=1, active=active,
                            )
                            assert status == "timeout"
                            assert perf is None
                            md.assert_called_once()
                            assert active == set()

    def test_create_failure_records_error_and_no_teardown(self):
        with patch.object(bench.endpoints_api, "create_workergroup",
                          side_effect=RuntimeError("boom")):
            with patch.object(bench.endpoints_api, "delete_workergroup") as md:
                with patch.object(bench.time, "monotonic", return_value=0):
                    active = set()
                    # Exception propagates out of _benchmark_one
                    with pytest.raises(RuntimeError):
                        bench._benchmark_one(
                            _mk_client(),
                            endpoint_id=1, endpoint_name="ep",
                            gpu_class="RTX 3060", num_gpus=1,
                            timeout=10, active=active,
                        )
                    # Nothing to delete — create never returned
                    md.assert_not_called()
                    assert active == set()

    def test_create_returns_no_id_reports_error(self):
        with patch.object(bench.endpoints_api, "create_workergroup",
                          return_value={"success": False}):
            with patch.object(bench.endpoints_api, "delete_workergroup") as md:
                with patch.object(bench.time, "monotonic", return_value=0):
                    active = set()
                    gpu, status, perf, err, price = bench._benchmark_one(
                        _mk_client(),
                        endpoint_id=1, endpoint_name="ep",
                        gpu_class="RTX 3060", num_gpus=1,
                        timeout=10, active=active,
                    )
                    assert status == "error"
                    assert "no id" in err
                    md.assert_not_called()

    def test_all_workers_terminal_bails_fast(self):
        # All workers in a terminal state (stopped) for >_TERMINAL_DEBOUNCE
        # without producing measured_perf -> fail fast. ``error`` is no longer
        # treated as terminal because the autoscaler restarts errored workers
        # via error -> rebooting -> model_loading.
        #
        # Two polls are needed: poll 1 sets `state_started` for worker 1,
        # poll 2 (clock advanced past the debounce) lets the per-worker
        # state-duration check fire.
        snapshot = []
        poll = [{"id": 1, "status": "stopped"}]
        with patch.object(bench.endpoints_api, "create_workergroup",
                          return_value={"success": True, "result": 1}):
            with patch.object(bench.endpoints_api, "get_endpoint_workers",
                              side_effect=[snapshot, poll, poll]):
                with patch.object(bench.endpoints_api, "delete_workergroup",
                                  return_value={}) as md:
                    with patch.object(bench.time, "sleep"):
                        # monotonic is consumed by: start (0), while-cond (0),
                        # _emit_progress's `now` (0) — sets state_started=0,
                        # terminal-check `now_ts` (5; under debounce, no fire),
                        # while-cond next iter (5), _emit_progress (50),
                        # terminal-check (50; > 30s, fires).
                        with patch.object(bench.time, "monotonic",
                                          side_effect=[0, 0, 0, 5, 5, 50, 50]):
                            active = set()
                            gpu, status, perf, err, price = bench._benchmark_one(
                                _mk_client(),
                                endpoint_id=1, endpoint_name="ep",
                                gpu_class="RTX 3060", num_gpus=1,
                                timeout=600, active=active,
                            )
                            assert status == "failed"
                            assert "terminal" in err
                            md.assert_called_once()

    def test_delete_failure_does_not_raise(self):
        # Snapshot is empty (no preexisting workers); poll then surfaces the
        # idle worker with measured_perf. Without the [empty, real] split, the
        # snapshot would catch worker 1 as preexisting and the polling loop
        # would filter it out.
        snapshot = []
        poll = [{"id": 1, "measured_perf": 5.0, "status": "idle"}]
        with patch.object(bench.endpoints_api, "create_workergroup",
                          return_value={"success": True, "result": 1}):
            with patch.object(bench.endpoints_api, "get_endpoint_workers",
                              side_effect=[snapshot, poll]):
                with patch.object(bench.endpoints_api, "delete_workergroup",
                                  side_effect=RuntimeError("delete failed")):
                    with patch.object(bench.time, "sleep"):
                        with patch.object(bench.time, "monotonic",
                                          side_effect=[0, 0, 1]):
                            # Should not raise; delete failure is logged
                            gpu, status, perf, err, price = bench._benchmark_one(
                                _mk_client(),
                                endpoint_id=1, endpoint_name="ep",
                                gpu_class="RTX 3060", num_gpus=1,
                                timeout=60, active=set(),
                            )
                            assert status == "ok"


# ---------------------------------------------------------------------------
# CLI integration: args.func(args) with mocked client + API
# ---------------------------------------------------------------------------


_FAKE_TEMPLATE = {"id": 99999, "hash_id": "x", "extra_filters": "{}"}


def _run_cli(parse_argv, patch_get_client, argv, *, create_resp, workers_seq,
             rental_dph=None, template=None, preflight_offers=1):
    """Parse argv and invoke the command with API mocks.

    `rental_dph` is the value the show_instance mock will return as
    `dph_total` for any successful rental (so the result table's
    `rental_dph` and `perf_per_dollar` columns get a known value).

    `preflight_offers` is the count returned by the pre-flight offer search;
    set to 0 to simulate the "no offers match this template" path.
    """
    template = template if template is not None else _FAKE_TEMPLATE
    fake_offer_list = [{"id": i} for i in range(preflight_offers)]
    instance_resp = {"dph_total": rental_dph} if rental_dph is not None else {}

    # _benchmark_one snapshots existing workers before creating the workergroup,
    # so prepend an empty list to whatever poll responses the caller wanted.
    workers_seq_with_snapshot = [[]] + list(workers_seq)
    with patch.object(bench.offers_api, "search_templates",
                      return_value=[template]):
        with patch.object(bench.offers_api, "search_offers",
                          return_value=fake_offer_list):
            with patch.object(bench.instances_api, "show_instance",
                              return_value=instance_resp):
                with patch.object(bench.endpoints_api, "create_endpoint",
                                  return_value={"success": True, "result": 11}):
                    with patch.object(bench.endpoints_api, "delete_endpoint",
                                      return_value={}):
                        with patch.object(bench.endpoints_api, "create_workergroup",
                                          return_value=create_resp):
                            with patch.object(bench.endpoints_api,
                                              "get_endpoint_workers",
                                              side_effect=workers_seq_with_snapshot):
                                with patch.object(bench.endpoints_api,
                                                  "delete_workergroup",
                                                  return_value={}):
                                    with patch.object(bench.time, "sleep"):
                                        args = parse_argv(argv)
                                        return args.func(args)


class TestBenchmarkRunCLI:
    def test_happy_path_returns_rows(self, parse_argv, patch_get_client):
        result = _run_cli(
            parse_argv, patch_get_client,
            ["benchmark", "run", "--template-id", "99999",
             "--gpus", "RTX_4080", "--timeout", "60", "-y", "--raw"],
            create_resp={"success": True, "result": 500},
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

    def test_missing_template_flag_errors(self, parse_argv, patch_get_client,
                                          capsys):
        args = parse_argv([
            "benchmark", "run", "--gpus", "RTX_3060",
            "--timeout", "60", "-y", "--raw",
        ])
        rc = args.func(args)
        assert rc == 2
        assert "template-id" in capsys.readouterr().err

    def test_endpoint_name_is_ephemeral(self, parse_argv, patch_get_client):
        with patch.object(bench.offers_api, "search_templates",
                          return_value=[_FAKE_TEMPLATE]), \
             patch.object(bench.offers_api, "search_offers",
                          return_value=[{"id": 1}]), \
             patch.object(bench.endpoints_api, "create_endpoint",
                          return_value={"success": True, "result": 1}) as ce, \
             patch.object(bench.endpoints_api, "delete_endpoint",
                          return_value={}), \
             patch.object(bench.endpoints_api, "create_workergroup",
                          return_value={"result": 2}), \
             patch.object(bench.endpoints_api, "get_endpoint_workers",
                          return_value=[{"measured_perf": 1.0}]), \
             patch.object(bench.endpoints_api, "delete_workergroup",
                          return_value={}), \
             patch.object(bench.time, "sleep"):
            args = parse_argv([
                "benchmark", "run", "--template-id", "99999",
                "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
            ])
            args.func(args)
            name = ce.call_args.kwargs["endpoint_name"]
            assert name.startswith("benchmark-")
            assert len(name) == len("benchmark-") + 8

    def test_endpoint_deleted_even_on_exception(self, parse_argv,
                                                patch_get_client):
        with patch.object(bench.offers_api, "search_templates",
                          return_value=[_FAKE_TEMPLATE]), \
             patch.object(bench.offers_api, "search_offers",
                          return_value=[{"id": 1}]), \
             patch.object(bench.endpoints_api, "create_endpoint",
                          return_value={"result": 1}), \
             patch.object(bench.endpoints_api, "delete_endpoint",
                          return_value={}) as de, \
             patch.object(bench.endpoints_api, "create_workergroup",
                          side_effect=RuntimeError("boom")), \
             patch.object(bench.endpoints_api, "delete_workergroup",
                          return_value={}), \
             patch.object(bench.time, "sleep"):
            args = parse_argv([
                "benchmark", "run", "--template-id", "99999",
                "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
            ])
            rows = args.func(args)
            assert rows[0]["status"] == "error"
            de.assert_called()

    def test_template_id_threaded_to_workergroup(self, parse_argv,
                                                 patch_get_client):
        with patch.object(bench.offers_api, "search_templates",
                          return_value=[_FAKE_TEMPLATE]), \
             patch.object(bench.offers_api, "search_offers",
                          return_value=[{"id": 1}]), \
             patch.object(bench.instances_api, "show_instance",
                          return_value={"dph_total": 0.5}), \
             patch.object(bench.endpoints_api, "create_endpoint",
                          return_value={"result": 1}), \
             patch.object(bench.endpoints_api, "delete_endpoint",
                          return_value={}), \
             patch.object(bench.endpoints_api, "create_workergroup",
                          return_value={"result": 2}) as cwg, \
             patch.object(bench.endpoints_api, "get_endpoint_workers",
                          return_value=[{"id": 7, "measured_perf": 1, "status": "idle"}]), \
             patch.object(bench.endpoints_api, "delete_workergroup",
                          return_value={}), \
             patch.object(bench.time, "sleep"):
            args = parse_argv([
                "benchmark", "run", "--template-id", "12345",
                "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
            ])
            args.func(args)
            assert cwg.call_args.kwargs["template_id"] == 12345

    def test_no_offers_skips_class(self, parse_argv, patch_get_client, capsys):
        # Pre-flight returns 0 offers — class should be skipped without ever
        # creating a workergroup.
        with patch.object(bench.offers_api, "search_templates",
                          return_value=[_FAKE_TEMPLATE]), \
             patch.object(bench.offers_api, "search_offers", return_value=[]), \
             patch.object(bench.endpoints_api, "create_endpoint",
                          return_value={"result": 1}), \
             patch.object(bench.endpoints_api, "delete_endpoint",
                          return_value={}), \
             patch.object(bench.endpoints_api, "create_workergroup") as cwg, \
             patch.object(bench.endpoints_api, "delete_workergroup",
                          return_value={}), \
             patch.object(bench.time, "sleep"):
            args = parse_argv([
                "benchmark", "run", "--template-id", "99999",
                "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
            ])
            rows = args.func(args)
            assert rows[0]["status"] == "no_offers"
            cwg.assert_not_called()

    def test_template_not_found_errors(self, parse_argv, patch_get_client,
                                       capsys):
        with patch.object(bench.offers_api, "search_templates", return_value=[]):
            args = parse_argv([
                "benchmark", "run", "--template-id", "99999",
                "--gpus", "RTX_3060", "--timeout", "60", "-y", "--raw",
            ])
            rc = args.func(args)
            assert rc == 1
            assert "not found" in capsys.readouterr().err
