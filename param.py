import os

############################################### set by the user
url_server = "193.48.28.112"
port_server = 8080

current_path = os.path.dirname(__file__)
devsimpy_path = '/opt/celine/'
devsimpy_dir = 'devsimpy'
devsimpy_version_dir = 'version-2.9'

block_path_dir = os.path.join(devsimpy_path, devsimpy_dir, devsimpy_version_dir, 'Domain')
devsimpy_nogui = os.path.join(devsimpy_path, devsimpy_dir, devsimpy_version_dir, 'devsimpy-nogui.py')

yaml_path_dir = os.path.join(current_path, 'static', 'yaml')
img_path_dir = os.path.join(current_path, 'static', 'img')

##################################################
