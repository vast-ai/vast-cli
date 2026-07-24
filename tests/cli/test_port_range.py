from vastai.cli.self_test.port_range import (
    PortRange,
    parse_port_range,
    port_range_docker_args,
    read_host_port_range,
    resolve_port_range,
    scan_mapped_port_range,
)


def test_parse_port_range_accepts_whitespace_and_rejects_invalid_values():
    assert parse_port_range(" 40000 - 40002\n") == PortRange(40000, 40002)
    assert parse_port_range("1023-40000") is None
    assert parse_port_range("40002-40000") is None
    assert parse_port_range("40000") is None


def test_read_and_resolve_port_range(tmp_path):
    path = tmp_path / "host_port_range"
    path.write_text("41000-41003\n", encoding="utf-8")

    assert read_host_port_range(str(path)) == PortRange(41000, 41003)
    port_range, source = resolve_port_range(host_path=str(path))
    assert port_range == PortRange(41000, 41003)
    assert source == "host_port_range"


def test_resolve_port_range_falls_back_to_instance_metadata(tmp_path):
    port_range, source = resolve_port_range(
        {"direct_port_start": 42000, "direct_port_end": 42002},
        host_path=str(tmp_path / "missing"),
    )
    assert port_range == PortRange(42000, 42002)
    assert source == "instance_metadata"


def test_docker_args_request_tcp_and_udp_range():
    assert port_range_docker_args(PortRange(40000, 40002)) == (
        "-p 40000-40002:40000-40002/tcp "
        "-p 40000-40002:40000-40002/udp"
    )


def test_scan_reports_missing_and_unreachable_mappings():
    instance = {
        "ports": {
            "40000/tcp": [{"HostPort": "50000"}, {"HostPort": "50000"}],
            "40000/udp": [{"HostPort": "50001"}],
            "40001/tcp": [{"HostPort": "50002"}],
        }
    }

    def fake_probe(public_ip, host_port, protocol, timeout):
        return {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": host_port != 50002,
            "error": "connection refused" if host_port == 50002 else None,
        }

    result = scan_mapped_port_range(
        instance,
        "203.0.113.10",
        PortRange(40000, 40001),
        probe=fake_probe,
    )

    assert result["status"] == "failed"
    assert result["mapped_entries"] == 3
    assert result["missing_mappings"] == [{"container_port": 40001, "protocol": "udp"}]
    assert result["failed"][0]["host_port"] == 50002
