import shutil

from api import app

if __name__ == "__main__":
    app.run()

    shutil.rmtree(app.config['UPLOAD_FOLDER'])
