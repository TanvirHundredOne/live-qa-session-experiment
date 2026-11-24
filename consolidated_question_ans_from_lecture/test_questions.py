import pandas as pd

def get_data(file_path):
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.lower()
    return df

df = get_data(file_path = "all_questions_v1.csv")
print("total qa sessions found:{}\nColumns in data:{}".format(df.shape[0], df.columns))
print()
print("sample data:\n", df.head(2).values)