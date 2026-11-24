from pathlib import Path
import pandas as pd
# Set the target directory (use "." for current directory)
target_dir = Path("./stanford_online")
dfs = pd.concat([pd.read_csv(file) for file in target_dir.rglob("*.csv")])


print(f"Total Q&A sessions found: {dfs.shape[0]}")
dfs.to_csv("consolidated_question_ans_from_lecture/consolidated_qas/temp_dump_stanford_online.csv",index=False)