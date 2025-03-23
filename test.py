from flask import Flask, request, jsonify
import sqlite3
import xml.sax

app = Flask(__name__)
DATABASE = 'database.db'

# Подключение к базе данных
def get_db():
    return sqlite3.connect(DATABASE)

# Инициализация базы данных
def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS Files (
            id INTEGER PRIMARY KEY, name TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS Tags (
            id INTEGER PRIMARY KEY, name TEXT, file_id INTEGER, 
            FOREIGN KEY (file_id) REFERENCES Files(id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS Attributes (
            id INTEGER PRIMARY KEY, name TEXT, value TEXT, tag_id INTEGER, 
            FOREIGN KEY (tag_id) REFERENCES Tags(id))''')

# Обработчик XML
class XMLHandler(xml.sax.ContentHandler):
    def __init__(self, file_id):
        self.file_id = file_id
        self.current_tag_id = None

    def startElement(self, name, attrs):
        with get_db() as db:
            cursor = db.execute('INSERT INTO Tags (name, file_id) VALUES (?, ?)', (name, self.file_id))
            self.current_tag_id = cursor.lastrowid
            for attr_name, attr_value in attrs.items():
                db.execute('INSERT INTO Attributes (name, value, tag_id) VALUES (?, ?, ?)', 
                           (attr_name, attr_value, self.current_tag_id))

# 1. Чтение XML-файла
@app.route('/api/file/read', methods=['POST'])
def read_file():
    if 'file' not in request.files:
        return jsonify(False)
    file = request.files['file']
    file_name = file.filename

    # Валидация XML
    try:
        # Сохраняем имя файла
        with get_db() as db:
            cursor = db.execute('INSERT INTO Files (name) VALUES (?)', (file_name,))
            file_id = cursor.lastrowid
        
        # Парсим XML
        parser = xml.sax.make_parser()
        parser.setContentHandler(XMLHandler(file_id))
        parser.parse(file)
    except xml.sax.SAXException:
        return jsonify(False)
    
    return jsonify(True)

# 2. Подсчет тегов
@app.route('/api/tags/get-count', methods=['GET'])
def get_tag_count():
    file_name = request.args.get('file_name')
    tag_name = request.args.get('tag_name')
    
    with get_db() as db:
        cursor = db.execute('SELECT id FROM Files WHERE name = ?', (file_name,))
        file_row = cursor.fetchone()
        if not file_row:
            return jsonify({'error': 'Файл не найден'}), 404
        file_id = file_row[0]
        
        cursor = db.execute('SELECT COUNT(*) FROM Tags WHERE file_id = ? AND name = ?', 
                           (file_id, tag_name))
        count = cursor.fetchone()[0]
        if count == 0:
            return jsonify({'error': 'В файле отсутствует тег с данным названием'}), 404
        return jsonify(count)

# 3. Получение атрибутов тега
@app.route('/api/tags/attributes/get', methods=['GET'])
def get_tag_attributes():
    file_name = request.args.get('file_name')
    tag_name = request.args.get('tag_name')
    
    with get_db() as db:
        cursor = db.execute('SELECT id FROM Files WHERE name = ?', (file_name,))
        file_row = cursor.fetchone()
        if not file_row:
            return jsonify({'error': 'Файл не найден'}), 404
        file_id = file_row[0]
        
        cursor = db.execute('''
            SELECT DISTINCT a.name 
            FROM Attributes a
            JOIN Tags t ON a.tag_id = t.id
            WHERE t.file_id = ? AND t.name = ?
        ''', (file_id, tag_name))
        attributes = [row[0] for row in cursor.fetchall()]
        if not attributes:
            return jsonify({'error': 'Тег не найден или у него нет атрибутов'}), 404
        return jsonify(attributes)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
