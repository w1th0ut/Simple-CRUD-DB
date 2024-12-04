from flask import Flask, render_template, request, redirect, url_for
import pymssql, os
from dotenv import load_dotenv, dotenv_values

load_dotenv()

app = Flask(__name__)

DB_CONFIG = {
    'host': os.getenv("HOST"),
    'user': os.getenv("USERDB"),
    'password': os.getenv("PASSWORD"),
    'database': os.getenv("DB")
}

def get_db_connection():
    return pymssql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database']
    )

def get_all_table_names():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'dbo'")
    tables = cursor.fetchall()
    connection.close()
    return [table[0] for table in tables]

def get_table_data(table_name):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
    columns = [column[0] for column in cursor.fetchall()]

    connection.close()
    return columns, rows

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/view_data', methods=['GET'])
@app.route('/view_data/<table_name>', methods=['GET'])
def view_data(table_name=None):
    tables = get_all_table_names()

    if request.args.get('table'):
        table_name = request.args.get('table')

    if table_name and table_name in tables:
        columns, rows = get_table_data(table_name)
    else:
        columns, rows = [], []

    return render_template('view_data.html', tables=tables, table_name=table_name, columns=columns, rows=rows)

@app.route('/query_data', methods=['GET', 'POST'])
def query_data():
    query_result = None
    query_error = None
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute(query)
                columns = [col[0] for col in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                query_result = {'columns': columns, 'rows': rows}
                connection.commit()
                connection.close()
            except Exception as e:
                query_error = str(e)
    return render_template('query_data.html', query_result=query_result, query_error=query_error, title="Query Data")

def get_columns_for_table(table_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s AND TABLE_SCHEMA = 'dbo'"
    cursor.execute(query, (table_name,))
    columns = [row[0] for row in cursor.fetchall()]
    conn.close()
    return columns

def get_all_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def insert_data_to_table(table_name, form_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    columns = ', '.join(form_data.keys())
    placeholders = ', '.join(['%s'] * len(form_data))
    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    values = list(form_data.values())
    try:
        cursor.execute(query, values)
        conn.commit()
    except Exception as e:
        print(f"Error inserting data: {e}")
    finally:
        conn.close()

def delete_data(table_name, form_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    column_name = list(form_data.keys())[0]
    value = form_data[column_name]
    query = f"DELETE FROM {table_name} WHERE {column_name} = %s"
    try:
        cursor.execute(query, (value,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        conn.close()

def get_primary_key(table_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = f"""
    SELECT column_name
    FROM information_schema.key_column_usage
    WHERE table_name = '{table_name}' AND constraint_name LIKE 'PK_%'
    """
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

@app.route('/insert_data', methods=['GET', 'POST'])
def insert_data():
    table_name = request.args.get('table')
    tables = get_all_tables()

    if table_name and table_name in tables:
        columns = get_columns_for_table(table_name)
        if request.method == 'POST':
            action = request.form.get('action')
            form_data = {key: value for key, value in request.form.items() if key != 'action'}
            if action == 'INSERT':
                insert_data_to_table(table_name, form_data)
            return redirect(url_for('insert_data', table=table_name))
        return render_template('insert_data.html', tables=tables, table_name=table_name, columns=columns)
    else:
        return render_template('insert_data.html', tables=tables, table_name=None)

@app.route('/delete_data', methods=['GET', 'POST'])
def delete_data():
    table_name = request.args.get('table')
    tables = get_all_tables()
    action = "DELETE"

    if table_name and table_name in tables:
        columns = get_columns_for_table(table_name)
        primary_key = get_primary_key(table_name)
        primary_key_index = columns.index(primary_key) if primary_key else 0
        rows = get_table_data(table_name)[1] if action == "DELETE" else []
        
        return render_template(
            'delete_data.html', 
            tables=tables, 
            table_name=table_name, 
            columns=columns, 
            rows=rows, 
            primary_key=primary_key, 
            primary_key_index=primary_key_index, 
            action=action
        )
    else:
        return render_template('delete_data.html', tables=tables, table_name=None)

@app.route('/delete_row', methods=['POST'])
def delete_row():
    table_name = request.form['table']
    key_column = request.form['key_column']
    key_value = request.form['key_value']
    conn = get_db_connection()
    cursor = conn.cursor()
    query = f"DELETE FROM {table_name} WHERE {key_column} = %s"
    try:
        cursor.execute(query, (key_value,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        conn.close()
    return redirect(url_for('delete_data', table=table_name))


if __name__ == '__main__':
    app.run(debug=True)