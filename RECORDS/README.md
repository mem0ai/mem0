# 测试locomo数据集：

第一步：add

```nohup python run_experiments.py --technique_type mem0 --method add > logs/0926_locomo_add.log 2>&1 &```

得到 memory

第二步：search

```nohup python run_experiments.py --technique_type mem0 --method search > logs/0926_locomo_search.log 2>&1 &```

得到结果，关于q & response的json

第三步：进行评估，计算指标

``` python evals.py --input_file results/{result}.json --output_file case_results.json```

统计平均得分

运行```evaluation/generate_scores.py```文件
