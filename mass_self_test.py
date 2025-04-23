import subprocess

machine_ids = [
    33931, 34006, 34017, 34036, 34061,
    34408, 34423, 34424, 34425, 34427, 34433
]

for machine_id in machine_ids:
    cmd = ["python3", "vast.py", "self-test", "machine", str(machine_id)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)

