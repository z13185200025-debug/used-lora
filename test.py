from openai import OpenAI
client = OpenAI(
    base_url='https://xiaoai.plus/v1',
    api_key='sk-d6HJ8wIh4bbnnjRmFu5UoUVS7IQwcL96nP6BKUJXpbpr5hYr'
)
completion = client.chat.completions.create(
  model="gpt-4o",
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ]
)
print(completion.choices[0].message)