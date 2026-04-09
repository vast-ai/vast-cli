# Implements an object oriented query language for Vast standard query (vast/web/apiquery.py)

from typing import Any, Optional


class Query:
    def __init__(self, query_dict: dict[str, dict[str, Any]]):
        # self.query has format {column : {op : value}}; may have multiple ops per column and multiple columns.
        self.query = query_dict

    @classmethod
    def search_defaults(
        cls,
        verified: Optional[bool] = True,
        rentable: Optional[bool] = True,
        rented: Optional[bool] = False,
    ) -> "Query":
        """Creates a Query pre-populated with default search filters for end-user use."""
        q = cls({})
        for name, value in [
            ("verified", verified),
            ("rentable", rentable),
            ("rented", rented),
        ]:
            if value is not None:
                q.query[name] = {"eq": value}
        return q

    def unparse_query(self) -> str:
        """Converts this Query back into a query string that parse_query() would parse into the same dict.

        Inverse of vast/web/parse.py:parse_query, i.e. parse_query(query.unparse_query()) == query.query.
        """
        op_to_str = {
            "eq": "=",
            "neq": "!=",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
            "in": " in ",
            "notin": " notin ",
        }
        # Fields whose values get multiplied by these factors during parsing
        mult_fields = {
            "cpu_ram": 1000,
            "gpu_ram": 1000,
            "gpu_total_ram": 1000,
            "duration": 24.0 * 60.0 * 60.0,
        }

        parts = []
        for field, ops in self.query.items():
            for op, value in ops.items():
                op_str = op_to_str[op]

                # Reverse the multiplier applied during parsing
                if field in mult_fields:
                    value = value / mult_fields[field]
                    # Use int if it's a whole number
                    if value == int(value):
                        value = int(value)

                # Format the value
                if isinstance(value, bool):
                    val_str = "true" if value else "false"
                elif value is None:
                    val_str = "None"
                elif isinstance(value, list):
                    # in/notin: reverse the space→underscore replacement per element
                    items = [str(v).replace(" ", "_") for v in value]
                    val_str = ",".join(items)
                elif isinstance(value, str):
                    # Reverse the underscore→space replacement done by parse_query
                    val_str = value.replace(" ", "_")
                else:
                    val_str = str(value)

                parts.append(f"{field}{op_str}{val_str}")
        return " ".join(parts)

    def extend(self, other: "Query") -> "Query":
        """
        Extends self.query with filters in other.

        self.query should now have all columns that exist in either self.query or other.query;
        and each column in self.query should have all corresponding ops in either query.
        """
        for column, ops in other.query.items():
            if column in self.query:
                conflicts = self.query[column].keys() & ops.keys()
                if conflicts:
                    raise ValueError(
                        f"Cannot redefine op(s) {conflicts} for column '{column}'"
                    )
                self.query[column].update(ops)
            else:
                self.query[column] = dict(ops)
        return self


class Column:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, value: Any) -> Query:
        return Query({self.name: {"eq": value}})

    def __ne__(self, value: Any) -> Query:
        return Query({self.name: {"neq": value}})

    def __lt__(self, value: Any) -> Query:
        return Query({self.name: {"lt": value}})

    def __le__(self, value: Any) -> Query:
        return Query({self.name: {"lte": value}})

    def __gt__(self, value: Any) -> Query:
        return Query({self.name: {"gt": value}})

    def __ge__(self, value: Any) -> Query:
        return Query({self.name: {"gte": value}})

    def in_(self, values) -> Query:
        return Query({self.name: {"in": values}})

    def notin_(self, values) -> Query:
        return Query({self.name: {"notin": values}})


# Pre-initialized Column objects for all columns in ask_contract_offers
id_ = Column("id")
ask_contract_id = Column("ask_contract_id")
bundle_id = Column("bundle_id")
bundled_results = Column("bundled_results")
bw_nvlink = Column("bw_nvlink")
compute_cap = Column("compute_cap")
cpu_arch = Column("cpu_arch")
cpu_cores = Column("cpu_cores")
cpu_cores_effective = Column("cpu_cores_effective")
cpu_ghz = Column("cpu_ghz")
cpu_name = Column("cpu_name")
cpu_ram = Column("cpu_ram")
credit_discount_max = Column("credit_discount_max")
cuda_max_good = Column("cuda_max_good")
direct_port_count = Column("direct_port_count")
disk_bw = Column("disk_bw")
disk_name = Column("disk_name")
disk_space = Column("disk_space")
dlperf = Column("dlperf")
dlperf_per_dphtotal = Column("dlperf_per_dphtotal")
dph_base = Column("dph_base")
dph_total = Column("dph_total")
driver_version = Column("driver_version")
driver_vers = Column("driver_vers")
duration = Column("duration")
end_date = Column("end_date")
external = Column("external")
flops_per_dphtotal = Column("flops_per_dphtotal")
geolocation = Column("geolocation")
geolocode = Column("geolocode")
gpu_arch = Column("gpu_arch")
gpu_display_active = Column("gpu_display_active")
gpu_frac = Column("gpu_frac")
gpu_ids = Column("gpu_ids")
gpu_lanes = Column("gpu_lanes")
gpu_mem_bw = Column("gpu_mem_bw")
gpu_name = Column("gpu_name")
gpu_ram = Column("gpu_ram")
gpu_total_ram = Column("gpu_total_ram")
gpu_max_power = Column("gpu_max_power")
gpu_max_temp = Column("gpu_max_temp")
has_avx = Column("has_avx")
host_id = Column("host_id")
hosting_type = Column("hosting_type")
hostname = Column("hostname")
inet_down = Column("inet_down")
inet_down_cost = Column("inet_down_cost")
inet_up = Column("inet_up")
inet_up_cost = Column("inet_up_cost")
is_bid = Column("is_bid")
logo = Column("logo")
machine_id = Column("machine_id")
min_bid = Column("min_bid")
mobo_name = Column("mobo_name")
num_gpus = Column("num_gpus")
os_version = Column("os_version")
pci_gen = Column("pci_gen")
pcie_bw = Column("pcie_bw")
public_ipaddr = Column("public_ipaddr")
reliability = Column("reliability")
reliability_mult = Column("reliability_mult")
rentable = Column("rentable")
rented = Column("rented")
score = Column("score")
start_date = Column("start_date")
static_ip = Column("static_ip")
storage_cost = Column("storage_cost")
storage_total_cost = Column("storage_total_cost")
total_flops = Column("total_flops")
verification = Column("verification")
vericode = Column("vericode")
vram_costperhour = Column("vram_costperhour")
webpage = Column("webpage")
vms_enabled = Column("vms_enabled")
expected_reliability = Column("expected_reliability")
is_vm_deverified = Column("is_vm_deverified")
resource_type = Column("resource_type")
cluster_id = Column("cluster_id")
avail_vol_ask_id = Column("avail_vol_ask_id")
avail_vol_dph = Column("avail_vol_dph")
avail_vol_size = Column("avail_vol_size")
nw_disk_min_bw = Column("nw_disk_min_bw")
nw_disk_max_bw = Column("nw_disk_max_bw")
nw_disk_avg_bw = Column("nw_disk_avg_bw")
platform_fee = Column("platform_fee")

# Virtual columns accepted by the API that are converted to real column(s) by search_asks_
# (see vast/web/views/misc.py)
geolocation = Column("geolocation")  # hashed → geolocode
datacenter = Column("datacenter")  # bool → hosting_type {eq: 0|1}
duration = Column("duration")  # seconds from now → end_date
verified = Column("verified")  # bool → vericode
allocated_storage = Column("allocated_storage")  # GB → disk_space {gte: value}
target_reliability = Column(
    "target_reliability"
)  # float → expected_reliability {gte: value}

# Column aliases (remapped to real columns before querying)
reliability2 = Column("reliability2")  # → reliability
dphtotal = Column("dphtotal")  # → dph_total
gpu_totalram = Column("gpu_totalram")  # → gpu_total_ram
gpu_totalram_GB = Column("gpu_totalram_GB")  # → gpu_total_ram (value * 1000)
cpu_ram_GB = Column("cpu_ram_GB")  # → cpu_ram (value * 1000)
gpu_ram_GB = Column("gpu_ram_GB")  # → gpu_ram (value * 1000)
ubuntu_version = Column("ubuntu_version")  # → os_version
driver_version = Column("driver_version")  # → driver_vers


# ---------------------------------------------------------------------------
# GPU name constants (from vast/controller/gpulist.json, column [1])
#
# Usage:  gpu_name == RTX_4090   or   gpu_name.in_([RTX_4090, RTX_4090_Ti])
# ---------------------------------------------------------------------------

# NVIDIA Data-Center / AI
A10 = "A10"
A10g = "A10g"
A16 = "A16"
A30 = "A30"
A40 = "A40"
A100_PCIE = "A100 PCIE"
A100_SXM4 = "A100 SXM4"
A100_SXM = "A100 SXM"
A100X = "A100X"
A800_PCIE = "A800 PCIE"
B200 = "B200"
GH200_SXM = "GH200 SXM"
H100_PCIE = "H100 PCIE"
H100_SXM = "H100 SXM"
H100_NVL = "H100 NVL"
H200 = "H200"
H200_NVL = "H200 NVL"
L4 = "L4"
L40 = "L40"
L40S = "L40S"
Tesla_K20c = "Tesla K20c"
Tesla_K80 = "Tesla K80"
Tesla_M40 = "Tesla M40"
Tesla_P4 = "Tesla P4"
Tesla_P6 = "Tesla P6"
Tesla_P40 = "Tesla P40"
Tesla_P100 = "Tesla P100"
Tesla_T4 = "Tesla T4"
Tesla_V100 = "Tesla V100"

# NVIDIA Consumer – GeForce / GTX
GeForce_970 = "GeForce 970"
GTX_750_Ti = "GTX 750 Ti"
GTX_1050 = "GTX 1050"
GTX_1050_Ti = "GTX 1050 Ti"
GTX_1060 = "GTX 1060"
GTX_1070 = "GTX 1070"
GTX_1070_Ti = "GTX 1070 Ti"
GTX_1080 = "GTX 1080"
GTX_1080_Ti = "GTX 1080 Ti"
GTX_1650 = "GTX 1650"
GTX_1650_S = "GTX 1650 S"
GTX_1650_Ti = "GTX 1650 Ti"
GTX_1660 = "GTX 1660"
GTX_1660_S = "GTX 1660 S"
GTX_1660_Ti = "GTX 1660 Ti"
GTX_TITAN_X = "GTX TITAN X"

# NVIDIA Consumer – RTX 20-series
RTX_2060 = "RTX 2060"
RTX_2060S = "RTX 2060S"
RTX_2070 = "RTX 2070"
RTX_2070S = "RTX 2070S"
RTX_2080 = "RTX 2080"
RTX_2080S = "RTX 2080S"
RTX_2080_Ti = "RTX 2080 Ti"

# NVIDIA Consumer – RTX 30-series
RTX_3050 = "RTX 3050"
RTX_3060 = "RTX 3060"
RTX_3060_laptop = "RTX 3060 laptop"
RTX_3060_Ti = "RTX 3060 Ti"
RTX_3070 = "RTX 3070"
RTX_3070_laptop = "RTX 3070 laptop"
RTX_3070_Ti = "RTX 3070 Ti"
RTX_3080 = "RTX 3080"
RTX_3080_Ti = "RTX 3080 Ti"
RTX_3090 = "RTX 3090"
RTX_3090_Ti = "RTX 3090 Ti"

# NVIDIA Consumer – RTX 40-series
RTX_4060 = "RTX 4060"
RTX_4060_laptop = "RTX 4060 laptop"
RTX_4060_Ti = "RTX 4060 Ti"
RTX_4070 = "RTX 4070"
RTX_4070_laptop = "RTX 4070 laptop"
RTX_4070S = "RTX 4070S"
RTX_4070S_Ti = "RTX 4070S Ti"
RTX_4070_Ti = "RTX 4070 Ti"
RTX_4080 = "RTX 4080"
RTX_4080_laptop = "RTX 4080 laptop"
RTX_4080S = "RTX 4080S"
RTX_4090 = "RTX 4090"
RTX_4090D = "RTX 4090D"
RTX_4090_Ti = "RTX 4090 Ti"

# NVIDIA Consumer – RTX 50-series
RTX_5060 = "RTX 5060"
RTX_5060_Ti = "RTX 5060 Ti"
RTX_5070 = "RTX 5070"
RTX_5070_Ti = "RTX 5070 Ti"
RTX_5080 = "RTX 5080"
RTX_5090 = "RTX 5090"
RTX_5090_Ti = "RTX 5090 Ti"

# NVIDIA Consumer – Titan
Titan_RTX = "Titan RTX"
Titan_V = "Titan V"
TITAN_V_CEO = "TITAN V CEO"
Titan_X = "Titan X"
Titan_Xp = "Titan Xp"

# NVIDIA Professional – Quadro
Quadro_K620 = "Quadro K620"
Quadro_K2200 = "Quadro K2200"
Quadro_P2000 = "Quadro P2000"
Quadro_P4000 = "Quadro P4000"
Quadro_P5000 = "Quadro P5000"
Quadro_P6000 = "Quadro P6000"
Quadro_GP100 = "Quadro GP100"
Quadro_GV100 = "Quadro GV100"
Q_RTX_4000 = "Q RTX 4000"
Q_RTX_5000 = "Q RTX 5000"
Q_RTX_6000 = "Q RTX 6000"
Q_RTX_8000 = "Q RTX 8000"

# NVIDIA Professional – RTX A-series
RTX_A2000 = "RTX A2000"
RTX_A4000 = "RTX A4000"
RTX_A4500 = "RTX A4500"
RTX_A5000 = "RTX A5000"
RTX_A6000 = "RTX A6000"

# NVIDIA Professional – RTX Ada Generation
RTX_2000Ada = "RTX 2000Ada"
RTX_4000Ada = "RTX 4000Ada"
RTX_4500Ada = "RTX 4500Ada"
RTX_5000Ada = "RTX 5000Ada"
RTX_5880Ada = "RTX 5880Ada"
RTX_6000Ada = "RTX 6000Ada"

# NVIDIA Professional – RTX PRO (Blackwell)
RTX_PRO_4000 = "RTX PRO 4000"
RTX_PRO_4000_Mobile = "RTX PRO 4000 Mobile"
RTX_PRO_4500 = "RTX PRO 4500"
RTX_PRO_5000 = "RTX PRO 5000"
RTX_PRO_6000 = "RTX PRO 6000"
RTX_PRO_6000_S = "RTX PRO 6000 S"
RTX_PRO_6000_WS = "RTX PRO 6000 WS"
RTX_PRO_6000_Max_Q = "RTX PRO 6000 Max-Q"

# NVIDIA Mining / Other
CMP_50HX = "CMP 50HX"
CMP_170HX = "CMP 170HX"
P104_100 = "P104-100"
P106_100 = "P106-100"

# AMD Instinct
InstinctMI50 = "InstinctMI50"
InstinctMI100 = "InstinctMI100"
InstinctMI210 = "InstinctMI210"
InstinctMI250X = "InstinctMI250X"

# AMD Radeon Pro
PRO_W6800 = "PRO W6800"
PRO_W7800 = "PRO W7800"
PRO_W7900 = "PRO W7900"
Pro_V620 = "Pro V620"
Radeon_VII = "Radeon VII"
Radeon_Pro_VII = "Radeon Pro VII"

# AMD Radeon RX
RX_6800 = "RX 6800"
RX_6800_XT = "RX 6800 XT"
RX_6900_XT = "RX 6900 XT"
RX_6950_XT = "RX 6950 XT"
RX_7600 = "RX 7600"
RX_7700_XT = "RX 7700 XT"
RX_7800_XT = "RX 7800 XT"
RX_7900_GRE = "RX 7900 GRE"
RX_7900_XT = "RX 7900 XT"
RX_7900_XTX = "RX 7900 XTX"
