import os
from wsgiref.handlers import format_date_time
from flask import Flask, request, redirect
from flask_mysqldb import MySQL
from flask_restful import Resource, Api
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
import math
import datetime

UPLOAD_FOLDER = '/usr/local/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Initialize the app
app = Flask(__name__)

# Setup hidden variables for the app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = os.environ['MYSQL_DB_USERNAME']
app.config['MYSQL_PASSWORD'] = os.environ['MYSQL_DB_PASSWORD']
app.config['MYSQL_DB'] = os.environ['MYSQL_DB_DATABASE']

# Set up cors support for all routes
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set up API
api = Api(app)

# Set up MySQL
mysql = MySQL(app)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def find_parent(root, parent_id):
    # root = { dirs: [], photos: [] }
    # recursively find the parent dict
    for dir in root['dirs']:
        if dir['id'] == parent_id:
            return dir
    for dir in root['dirs']:
        return find_parent(dir, parent_id)

class Greeting(Resource):
    def get(self):
        # Return a table of contents for the API links below
        return {
            'api': [
                {
                    'url': '/database',
                    'method': 'GET',
                    'description': 'Verifies the integrity of the database contents with the filesystem'
                },
                {
                    'url': '/login',
                    'method': 'POST',
                    'description': 'Logs in a use to the admin panel'
                },
                {
                    'url': '/dirents',
                    'method': 'POST',
                    'description': 'Inserts a new directory entry into the database'
                },
                {
                    'url': '/dirents',
                    'method': 'GET',
                    'description': 'Returns a list of directory entries'
                },
                {
                    'url': '/dirents',
                    'method': 'DELETE',
                    'description': 'Deletes a directory entry from the database'
                }]}
        
api.add_resource(Greeting, '/')
class Database(Resource):
    def get(self):
        # Recursively sets all dirent names from upload folder
        stack = []
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            parent_val = None
            # Root folders should have parent set to 0
            if(root != UPLOAD_FOLDER):
                # Get the parent id from the database by querying the parent folder name
                parent_name = root.split('/')[-1]
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT id FROM Dirents WHERE name = %s", (parent_name, ))
                parent_val = cursor.fetchone()[0]
            for dir in dirs:
                cursor = mysql.connection.cursor()
                now = datetime.datetime.now()
                # Format date to YYYY-MM-DD hh:mm:ss EST format
                format_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
                # Insert the directory into the database
                query = "INSERT IGNORE INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
                path = root.split('uploads')[1] + '/'+ dir
                cursor.execute(query, (dir, parent_val, '1', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
                mysql.connection.commit()
                cursor.close()
                # Add the directory to the stack
                stack.append(root + '/' + dir)
            for photo in files: 
                cursor = mysql.connection.cursor()
                now = datetime.datetime.now()
                format_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
                query = "INSERT IGNORE INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
                path = root.split('uploads')[1] + '/' + photo
                cursor.execute(query, (photo, parent_val, '0', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
                mysql.connection.commit()
                cursor.close()
                stack.append(root + '/' + photo)
        return {'status': 'success', 'data': stack}
api.add_resource(Database, '/database')
class Login(Resource):
    def post(self):
        username = request.json['username']
        password = request.json['password']
        return {'response': 'Login successful', 'success': True} if username == os.environ['JSADMIN_USERNAME'] and password == os.environ['JSADMIN_PASSWORD'] else {'response': 'Login failed', 'success': False}
api.add_resource(Login, '/login')

class Dirents(Resource):
    def post(self):
        # Retrieve the name name from the request
        name = request.form['name']
        # Retrieve the parent name id from the request
        parent = request.form['parent']
        # Retrieve the type of name from the request (0 = photo, 1 = directory)
        direntType = request.form['type']
        # Make cursor
        cursor = mysql.connection.cursor()
        
        # Check if name already exists
        cursor.execute("SELECT * FROM Dirents WHERE name = %s", (name,))
        if cursor.rowcount > 0:
            return {'response': 'Dirent already exists', 'success': True}
        parent_path = ''
        # Query for the parent name path
        if parent: 
            cursor.execute("SELECT path FROM Dirents WHERE id = %s", (parent, ))
            parent_path = cursor.fetchone()[0]
        
        format_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path = parent_path + '/' + name
        # Insert the directory into the database
        if direntType == '1':
            query = "INSERT INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (name, parent, '1', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
            # Commit the changes to the database
            mysql.connection.commit()
            cursor.close()
                        
        elif direntType == '0':
            query = "INSERT INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (name, parent, '0', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
            # Commit the changes to the database
            mysql.connection.commit()
            cursor.close()
        
        # Make the directory or copy the image to the location specified by the variable path
        if direntType == '1':
            print('This is upload path: ' + UPLOAD_FOLDER[1:] + path)
            os.makedirs(UPLOAD_FOLDER[1:] + path)
        elif direntType == '0':
            file = request.files['file']
            file.save(UPLOAD_FOLDER[1:] + path)
        return {'response': 'Dirent created at: ' + os.path.join(app.config['UPLOAD_FOLDER'], path), 'success': True}
        
        
        
    def get(self):
        # Dirent Structure: id, name, parent_dirent, isDir, created_at, path
        root = {'dirs': [], 'photos': [] }
        # Get all the root directories
        cursor = mysql.connection.cursor()
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NULL"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url) in cursor.fetchall():
            if(isDir == 1):
                root['dirs'].append({'id': id, 'name': name, 'url': url, 'path': path, 'dirs': [], 'photos': [], 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
            else:
                im = Image.open(UPLOAD_FOLDER + path)
                width, height = im.size
                root['photos'].append({'id': id, 'name': name, 'src': url, 'width': width, 'height': height, 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
        # Get all the subdirectories
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NOT NULL"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url) in cursor.fetchall():
            parent = find_parent(root, parent_dirent)
            if(isDir == 1):
                parent['dirs'].append({'id': id, 'name': name, 'url': url, 'path': path, 'dirs': [], 'photos': [], 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
            else:
                im = Image.open(UPLOAD_FOLDER + path)
                width, height = im.size
                parent['photos'].append({'id': id, 'name': name, 'src': url, 'width': width, 'height': height, 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
        return {'response': 'Successfully retrieved all dirents', 'success': True, 'dirents': root}
    def delete(self):
        # Retrieve the dirent name from the request
        dirents = request.json['dirents']
        # Move all files to the 'other' dirent
        for dirent in dirents:
            for filename in os.listdir(app.config['UPLOAD_FOLDER'] + '/' + dirent):
                os.rename(app.config['UPLOAD_FOLDER'] + '/' + dirent + '/' + filename, app.config['UPLOAD_FOLDER'] + '/other/' + filename)
        # Delete dirent folders
        for dirent in dirents:
            if os.path.exists(app.config['UPLOAD_FOLDER'] + '/' + dirent):
                os.rmdir(app.config['UPLOAD_FOLDER'] + '/' + dirent)
        return {'response': 'Dirents successfully deleted', 'success': True}
api.add_resource(Dirents, '/dirents')




if __name__ == '__main__':
    app.run(debug=True , threaded=True)