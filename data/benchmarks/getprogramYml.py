import os
import yaml

# 新的结果列表
new_results = []

# 遍历selected_smtlib2文件夹下的.smt2文件，并将文件路径添加到新的结果列表中
for root, dirs, files in os.walk("/home/aaa/PlatQSF/data/benchmarks/smtlib_qf_nia"):
    for file in files:
        if file.endswith(".smt2"):
            benchmark_path = os.path.join(root, file)
            new_results.append({
                "benchmark": benchmark_path,
                "expected_sat": "unknown",
                "is_trivial": False
            })

# 创建新的YAML数据
new_yaml_data = {
    "results": new_results,
    "schema_version": 0
    }

# 写入新的YAML文件
with open("smtlib_qf_nia/smtlib_qf_nia.yml", "w") as yaml_file:
    yaml.dump(new_yaml_data, yaml_file, default_flow_style=False)

print("新的YAML文件已生成")
