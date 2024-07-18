import os
import mysql.connector
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from flask import Flask, request, jsonify

app = Flask(__name__)

# Define database configuration
db_config = {
    'user': 'your_db_user',
    'password': 'your_db_password',
    'host': 'your_db_host',
    'database': 'your_db_name'
}

def get_schema_from_database():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    schema_info = ""
    table_names = set()
    for table in tables:
        table_name = list(table.values())[0]
        table_names.add(table_name.lower())
        schema_info += f"Table: {table_name}\n"
        cursor.execute(f"SHOW COLUMNS FROM {table_name}")
        columns = cursor.fetchall()
        for column in columns:
            schema_info += f" - {column['Field']} ({column['Type']})\n"

    cursor.close()
    conn.close()

    return schema_info, table_names

def execute_query(query: str):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def convert_to_natural_language(data, natural_language_text: str) -> str:
    if not data:
        return "No data present in the database for the given prompt. Please provide correct data."

    prompt_template = """
    You are a helpful assistant that converts database query results into natural language responses.
    Here is the natural language request:
    {natural_language_text}

    Here are the query results:
    {data}

    Please write a response in natural language based on these results.
    """

    prompt = PromptTemplate(input_variables=["natural_language_text", "data"], template=prompt_template)
    response_chain = LLMChain(prompt=prompt, llm=llm)
    result = response_chain.run(natural_language_text=natural_language_text, data=data)
    return result.strip()

def natural_language_to_mysql_query(natural_language_text: str, table_names: set) -> str:
    if not any(table in natural_language_text.lower() for table in table_names):
        return "No data available regarding the given prompt, please provide a correct prompt."
    
    schema_info, _ = get_schema_from_database()
    result = llm_chain.run(schema_info=schema_info, natural_language_text=natural_language_text)
    return result.strip()

prompt_template = """
You are a helpful assistant that translates natural language into MySQL queries.
Here is the schema of the database:
{schema_info}

Here is the natural language request:
{natural_language_text}

Please write a MySQL query to fulfill this request.
"""

prompt = PromptTemplate(input_variables=["schema_info", "natural_language_text"], template=prompt_template)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=os.getenv('OPENAI_API_KEY'))
llm_chain = LLMChain(prompt=prompt, llm=llm)

@app.route('/query', methods=['POST'])
def query():
    data = request.json
    nl_text = data.get('natural_language_text')
    schema_info, table_names = get_schema_from_database()
    mysql_query_or_message = natural_language_to_mysql_query(nl_text, table_names)

    if "No data available regarding the given prompt" in mysql_query_or_message:
        return jsonify({"message": mysql_query_or_message})
    
    query_results = execute_query(mysql_query_or_message)
    natural_language_response = convert_to_natural_language(query_results, nl_text)
    return jsonify({"query": mysql_query_or_message, "results": query_results, "natural_language_response": natural_language_response})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
