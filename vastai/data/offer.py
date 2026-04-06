from dataclasses import dataclass
from typing import Optional


@dataclass
class Offer:
    """
    A search result offer from ask_contract_offers, as returned by /api/v0/bundles/.
    Field names match the API response keys.
    """
    id:                    int
    ask_contract_id:       Optional[int]
    machine_id:            int
    host_id:               int
    num_gpus:              int
    gpu_name:              str
    gpu_ram:               int            # MB
    gpu_total_ram:         Optional[int]  # MB
    gpu_frac:              Optional[float]
    gpu_arch:              Optional[str]
    gpu_lanes:             Optional[int]
    gpu_mem_bw:            Optional[float]
    gpu_max_power:         Optional[float]
    gpu_max_temp:          Optional[float]
    compute_cap:           Optional[int]
    cuda_max_good:         Optional[float]
    bw_nvlink:             Optional[float]
    cpu_name:              Optional[str]
    cpu_cores:             Optional[int]
    cpu_cores_effective:   Optional[float]
    cpu_ghz:               Optional[float]
    cpu_ram:               Optional[int]  # MB
    cpu_arch:              Optional[str]
    disk_space:            Optional[float]
    disk_bw:               Optional[float]
    disk_name:             Optional[str]
    inet_up:               Optional[float]
    inet_down:             Optional[float]
    inet_up_cost:          Optional[float]
    inet_down_cost:        Optional[float]
    direct_port_count:     Optional[int]
    pci_gen:               Optional[float]
    pcie_bw:               Optional[float]
    mobo_name:             Optional[str]
    os_version:            Optional[str]
    driver_vers:           Optional[int]
    has_avx:               Optional[int]
    dph_base:              Optional[float]
    dph_total:             Optional[float]
    min_bid:               Optional[float]
    dlperf:                Optional[float]
    dlperf_per_dphtotal:   Optional[float]
    flops_per_dphtotal:    Optional[float]
    total_flops:           Optional[float]
    score:                 Optional[float]
    vram_costperhour:      Optional[float]
    storage_cost:          Optional[float]
    storage_total_cost:    Optional[float]
    credit_discount_max:   Optional[float]
    rentable:              Optional[bool]
    rented:                Optional[bool]
    is_bid:                Optional[bool]
    external:              Optional[int]
    hosting_type:          Optional[int]
    hostname:              Optional[str]
    public_ipaddr:         Optional[str]
    geolocation:           Optional[str]
    geolocode:             Optional[int]
    reliability:           Optional[float]
    reliability_mult:      Optional[float]
    expected_reliability:  Optional[float]
    verification:          Optional[str]
    vericode:              Optional[int]
    static_ip:             Optional[bool]
    vms_enabled:           Optional[bool]
    is_vm_deverified:      Optional[bool]
    gpu_display_active:    Optional[bool]
    logo:                  Optional[str]
    webpage:               Optional[str]
    resource_type:         Optional[str]
    start_date:            Optional[float]
    end_date:              Optional[float]
    duration:              Optional[float]
    bundle_id:             Optional[int]
    bundled_results:       Optional[int]
    cluster_id:            Optional[int]
    avail_vol_ask_id:      Optional[int]
    avail_vol_dph:         Optional[float]
    avail_vol_size:        Optional[float]
    nw_disk_min_bw:        Optional[int]
    nw_disk_max_bw:        Optional[int]
    nw_disk_avg_bw:        Optional[int]
    platform_fee:          Optional[float]

    @classmethod
    def from_dict(cls, d: dict) -> "Offer":
        """Construct an Offer from a raw API response dict, ignoring unknown keys.
        Missing Optional fields default to None."""
        import dataclasses
        known = {f.name: f for f in dataclasses.fields(cls)}
        kwargs = {}
        for name, field in known.items():
            if name in d:
                kwargs[name] = d[name]
            elif hasattr(field.default, '__call__') or field.default is not dataclasses.MISSING:
                pass  # has a default, let dataclass handle it
            elif field.default_factory is not dataclasses.MISSING:
                pass  # has a default_factory
            else:
                # No default — use None for Optional fields, skip otherwise
                kwargs[name] = None
        return cls(**kwargs)
