import os
import mysql.connector
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from fuzzywuzzy import fuzz

app = FastAPI()

# Define database configuration
db_config = {
    'user': 'root',
    'password': '1234',
    'host': 'localhost',
    'database': 'task1'
}

# Initialize the language model
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=os.getenv('OPENAI_API_KEY'))

# Cache schema information
schema_info = ""
table_names = set()
column_names = set()

def get_schema_from_database():
    global schema_info, table_names, column_names
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    schema_info = ""
    table_names = set()
    column_names = set()
    for table in tables:
        table_name = list(table.values())[0]
        table_names.add(table_name.lower())
        schema_info += f"Table: {table_name}\n"
        cursor.execute(f"SHOW COLUMNS FROM {table_name}")
        columns = cursor.fetchall()
        for column in columns:
            column_names.add(column['Field'].lower())
            schema_info += f" - {column['Field']} ({column['Type']})\n"
        # Fetch foreign key relationships
        cursor.execute(f"""
            SELECT
                COLUMN_NAME, 
                REFERENCED_TABLE_NAME, 
                REFERENCED_COLUMN_NAME
            FROM
                information_schema.KEY_COLUMN_USAGE
            WHERE
                TABLE_NAME = '{table_name}' AND
                REFERENCED_TABLE_NAME IS NOT NULL
        """)
        foreign_keys = cursor.fetchall()
        for fk in foreign_keys:
            schema_info += f" - FK: {fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE_NAME']}({fk['REFERENCED_COLUMN_NAME']})\n"

    cursor.close()
    conn.close()

# Load schema information when the application starts
get_schema_from_database()

def execute_query(query: str):
    print(f"Executing query: {query}")  # Debugging line
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query)
        results = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        results = []
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

def natural_language_to_mysql_query(natural_language_text: str) -> str:
    global schema_info, table_names, column_names

    # Check for partial matches with fuzzy matching
    def is_match(text, names):
        return any(fuzz.partial_ratio(text.lower(), name) >= 60 for name in names)
    
    if not is_match(natural_language_text, table_names) and not is_match(natural_language_text, column_names):
        return "No data available regarding the given prompt, please provide a correct prompt."

    # Update the prompt to request only the SQL query
    prompt_template = """
    You are a SQL expert. I will provide you with a natural language request and the schema of the database. Please generate the MySQL query to fulfill the request. Provide only the MySQL query, with no additional text or explanation.

    Database Schema:
    {schema_info}

    Natural Language Request:
    {natural_language_text}

    MySQL Query:
    """

    prompt = PromptTemplate(input_variables=["schema_info", "natural_language_text"], template=prompt_template)
    response_chain = LLMChain(prompt=prompt, llm=llm)
    raw_response = response_chain.run(schema_info=schema_info, natural_language_text=natural_language_text)

    # Extract only the SQL query part from the response
    if "MySQL Query:" in raw_response:
        start_index = raw_response.index("MySQL Query:") + len("MySQL Query:")
        sql_query = raw_response[start_index:].strip()
    else:
        sql_query = raw_response.strip()

    return sql_query

prompt_template = """
You are a helpful assistant that translates natural language into MySQL queries.
Here is the schema of the database:
{schema_info}

Here is the natural language request:
{natural_language_text}

Please write a MySQL query to fulfill this request.
"""

# Initialize the LLM chain
prompt = PromptTemplate(input_variables=["schema_info", "natural_language_text"], template=prompt_template)
llm_chain = LLMChain(prompt=prompt, llm=llm)

class QueryRequest(BaseModel):
    natural_language_text: str

@app.post("/query")
async def query(request: QueryRequest):
    nl_text = request.natural_language_text
    mysql_query_or_message = natural_language_to_mysql_query(nl_text)

    if "No data available regarding the given prompt" in mysql_query_or_message:
        return {"message": mysql_query_or_message}
    
    query_results = execute_query(mysql_query_or_message)
    natural_language_response = convert_to_natural_language(query_results, nl_text)
    return {"query": mysql_query_or_message, "results": query_results, "natural_language_response": natural_language_response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
