from bottle import default_app, route, debug, static_file, response, request

import os
import subprocess
import time
import json
import signal
import socket
from datetime import datetime
import pymongo
from pymongo import MongoClient 
from bson import objectid
import traceback

import __builtin__
from compiler.pyassem import Block

#import BaseDEVS, DomainBehavior, DomainStructure

__builtin__.__dict__['DEVS_DIR_PATH_DICT'] = {}

from param import * 

### global variables
global_running_sim = {}  

BLOCK_FILE_EXTENSIONS = ['.amd', '.cmd', '.py']
IMG_FILE_EXTENSIONS = ['.jpg', '.JPG']

# the decorator
def enable_cors(fn):
    def _enable_cors(*args, **kwargs):
        # set CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

        if request.method != 'OPTIONS':
            #'OPTIONS' method is used for Cross-Origin Requests preflight
            # see https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS
            # actual request; reply with the actual response
            return fn(*args, **kwargs)

    return _enable_cors

############################################################################
#
#       Functions
#
############################################################################

def getYAMLFile(name):
    """ Get yaml file
    """
    filenames = [entry for entry in os.listdir(yaml_path_dir)]

    return dict([(name, open(os.path.join(yaml_path_dir, name), 'r').read())])\
    if name in filenames else {}


def getYAMLFilenames():
    """ Get all yamls file names in yaml_path_dir
    """
    model_list = []
    #model_list = {}
    for entry in os.listdir(yaml_path_dir):
        
        if entry.endswith('.yaml'):
            model_name = entry.split('.')[0]
            filename = os.path.join(yaml_path_dir, entry)
            """model_list[model_name] = {
                               'filename'     : filename,
                               'last_modified': str(time.ctime(os.path.getmtime(filename))), 
                               'size'         : str(os.path.getsize(filename)*0.001)+' ko'}
            """
            model_list.append({'model_name'   : model_name,
                               'filename'     : filename,
                               'last_modified': str(time.ctime(os.path.getmtime(filename))), 
                               'size'         : str(os.path.getsize(filename)*0.001)+' ko'})
            
    return model_list


def getModelAsJSON(model_filename):
    """ Run a script to translate the YAML model description to JSON
    """
    if model_filename.endswith('.yaml'):
        model_abs_filename = os.path.join(yaml_path_dir, model_filename)
        ### execute command as a subprocess
        cmd = ["python2.7", devsimpy_nogui, model_abs_filename, "-json"]
        output = subprocess.check_output(cmd) 
    else:
        output = "unexpected filename : " + model_filename

    return output

def group(lst, n):
    """group([0,3,4,10,2,3], 2) => [(0,3), (4,10), (2,3)]

    Group a list into consecutive n-tuples. Incomplete tuples are
    discarded e.g.

    >>> group(range(10), 3)
    [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    """
    return zip(*[lst[i::n] for i in range(n)])

def getJointJs(d):
    """ return the json for JOIN
    """
    ### get param coming from url
    name = request.params.name

    ### list of ConnectinShape, CodeBlock, ContainerBlock
    docs = []
    l = d[name].split('\r\n')

    for i,raw_doc in enumerate(l):
        if raw_doc and ("!!python/object:" in raw_doc or 'label: !!python/unicode' in raw_doc):
            docs.append(raw_doc)

    ### return list of tuples of connected models
    return str(group(map(lambda b: b.split(' ')[-1], filter(lambda a: 'label' in a, docs)),2))


############################################################################
#
#       Routes
#
############################################################################
@route('/img/<filepath:path>')
def server_img(filepath):
    return static_file(filepath, root=os.path.join(current_path,'static','img'))

############################################################################
@route('/dsp/<filepath:path>')
def server_dsp(filepath):
    return static_file(filepath, root=os.path.join(current_path,'static','dsp'))

############################################################################
#   HOME
############################################################################

@route('/')
@enable_cors
def serve_homepage():
    return static_file('index.html', root=os.path.join(current_path, 'static'))

############################################################################
#   SERVER INFORMATION
############################################################################

@route('/info', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_info():
    """ Get server info
    """
    from platform import python_version

    data = {'devsimpy-version':os.path.basename(os.path.dirname(devsimpy_nogui)),
            'devsimpy-libraries': filter(lambda a: a not in [".directory", "Basic", "__init__.py"], os.listdir(os.path.join(os.path.dirname(devsimpy_nogui), 'Domain'))),
            'python-version': python_version(),
            ### TODO read __init__.py to build plugins list
            'devsimpy-plugins':filter(lambda a: a not in ["__init__.py"], os.listdir(os.path.join(os.path.dirname(devsimpy_nogui), 'plugins'))),
            'url-server':url_server,
            'machine-server': subprocess.check_output("uname -m", shell=True),
            'os-server': subprocess.check_output("uname -o", shell=True),
            'machine-version-server': subprocess.check_output("uname -v", shell=True)
            }
    return data

############################################################################
#   RESOURCE = MASTER MODEL
############################################################################
#   Models collection
############################################################################

@route('/models', method=['OPTIONS','GET'])
@enable_cors
def models_list():
    """ Return the list of the models available on the server
        with filename, date and size
    """
    list = getYAMLFilenames()

    return {'models' : list}

#   Model creation
############################################################################
@route('/models', method=['OPTIONS','POST'])
@enable_cors
def create_model():
    
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext != '.yaml':
        return {'success' : False, 'filename':upload.filename, 'info': 'Only .yaml file allowed.'}
    
    if os.path.exists(os.path.join(yaml_path_dir, name+ext)):
        return {'success' : False , 'filename':upload.filename, 'info' : 'File already exists'}
    
    upload.save(yaml_path_dir, overwrite=False) # appends upload.filename automatically
    #os.chmod(os.path.join(yaml_path_dir, (name + ext)), stat.S_IWGRP)
    # TODO add a check on the yaml file
    return {'success' : True, 'model_name':name}
    #except:
    #    import traceback
    #    return {'success' : False , 'info' : traceback.format_exc()}

    
#   Model update
############################################################################
@route('/models/<model_name>', method=['OPTIONS','POST'])
@enable_cors
def update_model(model_name):
    
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext != '.yaml':
        return {'success' : False, 'filename':upload.filename, 'info': 'Only .yaml file allowed.'}
    if name != model_name: 
        return {'success' : False, 'filename':upload.filename, 'model_name':model_name, 'info': 'Filename does not match model_name.'}
    upload.save(yaml_path_dir, overwrite=True) # appends upload.filename automatically
    # TODO add a check on the yaml file
    return {'success' : True, 'model_name':name}
    

#   Model deletion
############################################################################
@route('/models/<model_name>', method=['OPTIONS','DELETE'])
@enable_cors
def model_delete(model_name):

    model_abs_filename = os.path.join(yaml_path_dir, model_name+'.yaml')
    
    if os.path.exists(model_abs_filename):
        os.remove(model_abs_filename)
    
    return {'success' : True, 'model_name':model_name}
    

#   Model representation
############################################################################

@route('/models/<model_name>', method=['OPTIONS','GET'])
@enable_cors
def model_representation(model_name):
    """ Return the representation of the model
        according to requested content type
    """
    model_filename = model_name + '.yaml'
    if request.headers['Accept'] == 'application/json':
        data = getModelAsJSON(model_filename)
        return {"success"    : data!={} and data!=[],
                "model_name" : model_name, 
                "model"      : json.loads(data)}
    elif request.headers['Accept'] == 'text/x-yaml':
        data = getYAMLFile(model_filename)
        return {"success"    : data!={} and data!=[],
                "model_name" : model_name, 
                "model"      : data }
    else:
        return {"success"   : False, 
                "model_name": model_name, 
                "info"      : "unexpected Accept type = " + request.headers['Accept']}

    
############################################################################
#    RESOURCE = ATOMIC MODEL CODE
############################################################################
#   Blocks collection : no need for a global list of available blocks yet
############################################################################

#   Block creation
############################################################################
@route('/codeblocks', method=['OPTIONS','POST'])
@enable_cors
def create_codeblock():
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext not in BLOCK_FILE_EXTENSIONS:
        return {'success' : False, 'filename':upload.filename, 'info': 'Only .amd, .cmd and .py files allowed.'}
    
    if os.path.exists(os.path.join(block_path_dir, name+ext)):
        return {'success' : False , 'filename':upload.filename, 'info' : 'File already exists'}
    
    upload.save(block_path_dir, overwrite=False) # appends upload.filename automatically
    # TODO add a check on file validity
    return {'success' : True, 'block_name':name}

    
#   Block update
############################################################################
@route('/codeblocks/<block_name>', method=['OPTIONS','POST'])
@enable_cors
def update_codeblock(block_name):

    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext not in BLOCK_FILE_EXTENSIONS:
        return {'success' : False, 'filename':upload.filename, 'info': 'Only .amd, .cmd and .py files allowed.'}
    if name != block_name: 
        return {'success' : False, 'filename':upload.filename, 'block_name': block_name, 'info': 'Filename does not match block_name.'}

    upload.save(block_path_dir, overwrite=True) # appends upload.filename automatically
    # TODO add a check on file validity
    return {'success' : True, 'block_name':name}


#   Block deletion
############################################################################
@route('/codeblocks/<block_name>', method=['OPTIONS','DELETE'])
@enable_cors
def delete_codeblock(block_name):
    block_abs_filename = os.path.join(block_path_dir, block_name)
    
    for ext in BLOCK_FILE_EXTENSIONS:
        if os.path.exists(block_abs_filename + ext):
            os.remove(block_abs_filename + ext)
    
    return {'success' : True, 'block_name':block_name}


#   Blocks collection within a model
############################################################################
@route('/models/<model_name>/atomics', method=['OPTIONS','GET'])
@enable_cors
def model_atomicblocks_list(model_name):
    """ get the model blocks list from yaml
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, os.path.join(yaml_path_dir, model_name + '.yaml'), "-blockslist"]
    output = subprocess.check_output(cmd)

    try:
        blocks = json.loads(output)
        return {'success'     : True, 
                'model_name'  : model_name,
                'blocks'      : blocks}
    except:
        return {'success'     : False, 
                'model_name'  : model_name,
                'info'        : output}


#   Block parameters (for a given model)
############################################################################
@route('/models/<model_name>/atomics/<block_label>/params', method=['OPTIONS','GET'])
@enable_cors
def model_atomicblock_parameters(model_name, block_label):
    """ get the parameters of the block
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, os.path.join(yaml_path_dir, model_name + '.yaml'), "-blockargs", block_label]
    output = subprocess.check_output(cmd)
    
    try:
        params = json.loads(output)
        return {'success'     : True, 
                'model_name'  : model_name,
                'block_label' : block_label,
                'block'       : params}
    except:
        return {'success'     : False, 
                'model_name'  : model_name,
                'block_label' : block_label,
                'info'        : output}


#   Block parameters update (for a given model)
#   body example : {"maxStep":1, "maxValue":100, "minStep":1, "minValue":0, "start":0}
############################################################################
@route('/models/<model_name>/atomics/<block_label>/params', method=['OPTIONS','PUT'])
@enable_cors
def save_yaml(model_name, block_label):
    """ Update yaml file from devsimpy-mob
    """
    # update filename to absolute path
    model_abs_filename = os.path.join(yaml_path_dir, model_name + '.yaml')
    # Get the new parameters as from JSON from request body
    data = request.json
        
    # perform update (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, model_abs_filename, "-blockargs", block_label, "-updateblockargs", json.dumps(data)]
    output = subprocess.check_output(cmd)
    #return {'output' : output}
    #print(output)
    try:
        params = json.loads(output)
        return {'success'     : True, 
                'model_name'  : model_name,
                'block_label' : block_label,
                'block'       : params}
    except:
        return {'success'     : False, 
                'model_name'  : model_name,
                'block_label' : block_label,
                'info'        : output}

#   Image creation
############################################################################
def add_unique_postfix(fn):
    if not os.path.exists(os.path.join(img_path_dir,fn)):
        return fn

    name, ext = os.path.splitext(fn)

    make_fn = lambda i: '%s_%d%s' % (name, i, ext)

    for i in xrange(2, 1000):
        uni_fn = make_fn(i)
        if not os.path.exists(os.path.join(img_path_dir, uni_fn)):
            return uni_fn

    return None

@route('/models/<model_name>/atomics/<block_label>/images', method=['OPTIONS','POST'])
@enable_cors
def create_image(model_name, block_label):
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext not in IMG_FILE_EXTENSIONS:
        return {'success'  : False, 
                'filename' : upload.filename,
                'info'     : 'Only .jpg files allowed.'}
    
    new_filename = model_name + '_' + block_label + '_' + name + ext
    upload.filename = add_unique_postfix(new_filename)
    #upload.filename = os.tempnam(img_path_dir) # unsafe...
    
    upload.save(img_path_dir, overwrite=False) # appends upload.filename automatically
    
    return {'success'        : True,
            'model_name'     : model_name,
            'block_label'    : block_label,
            'image_filename' : upload.filename}

#   Image GET
############################################################################
@route('/models/<model_name>/atomics/<block_label>/images/<img_name>', method=['OPTIONS','GET'])
@enable_cors
def get_image(model_name, block_label, img_name):
    name, ext = os.path.splitext(img_name)
        
    if ext not in IMG_FILE_EXTENSIONS:
        return {'success' : False, 'info': 'Only .jpg files allowed.'}
    
    filename = os.path.join(img_path_dir, img_name)
    if not os.path.exists(filename):
        return {'success' : False, 'info': 'File does not exits.', 'filename':filename}
    
    return static_file(img_name, root=img_path_dir, download=img_name)

############################################################################
#    RESOURCE = SIMULATION
############################################################################
#    Common services
############################################################################
def update_status (simu_name):
    """
        Test if the simulation exists and
        if it does, tests if it is still alive
        possible statuses : RUNNING / PAUSED / FINISHED / UNKNOWN
    """
    simu = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
    
    if simu == None:
        return "UNKNOWN"

    if simu['status'] != 'FINISHED':
        try:
            # check on process status
            simu_process = global_running_sim[simu_name]
            simu_process.poll()
            returncode = simu_process.returncode
        
            # test if process is finished <=> (returnCode != None)
            if (returncode != None):
                # update status
                simu['status'] = "FINISHED"
                simu['exit_code']= returncode
                
                # get report
                with open(simu_name+'.report', 'r') as fout:
                    report = fout.read()
                    json_report = json.loads(report)
                    simu['report'] = json_report
                    
                del global_running_sim[simu_name]
                
                with open(simu_name+'.log', 'r') as flog:
                    simu['log'] = flog.read()   
                    
                with open(simu_name+'.err', 'r') as ferr:
                    simu['error'] = ferr.read()  
                    if simu['error'] != '':
                        simu['report']['success']=False
                
        except:
            # Simulation is marked as RUNNING but process cannot be found
            # might happen in case of server reboot...
            simu['status'] = "FINISHED"
            simu['exit_code'] = "UNEXPECTED_END"
            if 'report' not in simu:
                simu['report'] = {'success':False, 'output':[]}# for compatibility
            simu['error'] = traceback.format_exc()
            #raise
        
        # update in database                 
        db.simulations.replace_one ({'_id' : objectid.ObjectId(simu_name)}, simu)
    
    return simu['status']


def pause_or_resume (simu_name, action):
    """
    """
    current_status = update_status (simu_name)

    if current_status in ("RUNNING", "PAUSED"):
        CONVERT = {
            'PAUSE'  : {'expected_thread_status' : 'PAUSED',  'sim_status': "PAUSED"},
            'RESUME' : {'expected_thread_status' : 'RESUMED', 'sim_status': "RUNNING"}}

        thread_json_response = send_via_socket(simu_name, action)
        
        try:
            thread_status = thread_json_response['status']
        
            if thread_status == CONVERT[action]['expected_thread_status']:
                db.simulations.find_one_and_update({'_id' : objectid.ObjectId(simu_name)},
                                                   {'$set': {'status' : CONVERT[action]['sim_status']}})
                return {'success'         : True, 
                        'simulation_name' : simu_name,
                        'status'          : thread_status, 
                        'simulation_time' : thread_json_response['simulation_time']}
            else:
                return {'success' : False,  
                        'simulation_name' : simu_name,
                        'status'  : thread_status, 
                        'expected': CONVERT[action]['expected_thread_status']}
        except:
            raise
            return {'success': False,  
                    'simulation_name' : simu_name,
                    'status': thread_response}
            
    else: 
        return {'success':False, 
                'simulation_name' : simu_name,
                'status': current_status} 

def send_via_socket(simu_name, data):
    """ send data string to the simulation identified by simu_name
    """
    try:
        simu = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
        socket_address = '\0' + 'socket_' + simu_name
        comm_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        #socket_address = ('localhost', 5555)
        #comm_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        comm_socket.connect((socket_address))
        comm_socket.sendall(data)
        status = comm_socket.recv(1024)
        json_status = json.loads(status)
        comm_socket.close()
    except:
        # Usually because SocketSever is not yet operational
        json_status = {'status':"SOCKET_ERROR"}
        comm_socket.close()
        #raise 

    return json_status


#    Simulations collection
############################################################################
@route('/simulations', method=['OPTIONS','GET'])
@enable_cors
def simulations_list():
    """
    """
    simu_list = []
    n = 0
        
    cursor = db.simulations.find().sort([("internal_date", pymongo.DESCENDING)])
    # possibility to add a filter on the username
    # !!! Order by date is not preserved, JSON is ordered by alphabetical key order...
    
    for simu in cursor:
        simu_name = str(simu['_id'])
        simu_list.append({'simulation_name' : simu_name,
                          'info'            : simu})
        n+=1
        
        if simu['status'] != 'FINISHED': 
            update_status(simu_name)
            simu_list[n-1]['info'] = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
        
        # Handle Mongo non serializable fields TBC
        del simu_list[n-1]['info']['_id'] 
        del simu_list[n-1]['info']['internal_date']
       
    return {'simulations' : simu_list} 


#    Simulation creation
#    body example :  {"model_filename":"test.yaml", "simulated_duration":"50"}
############################################################################
@route('/simulations', method=['OPTIONS','POST'])
@enable_cors
def simulate():
    """
    """
    ### Get data from JSON body
    data = request.json
    
    ### Check that the given model name is valid
    model_filename     = data['model_name'] + '.yaml'
    abs_model_filename = os.path.join(yaml_path_dir, model_filename)
    if not os.path.exists(abs_model_filename):
        return {'success':False, 'info': "file does not exist! "+ abs_model_filename}

    ### Check that the given simulation duration is valid
    sim_duration = data['simulated_duration']
    if sim_duration in ('ntl', 'inf'):
        sim_duration = "10000000"
    if not str(sim_duration).isdigit():
        return {'success':False, 'info': "time must be digit!"}

    ### Delete old result files .dat
    ### TODO : improve result file management
    ###        currently, 2 simulations with the same model will erase and write the same file...
    for result_filename in filter(lambda fn: fn.endswith('.dat') and fn.startswith(data['model_name']), os.listdir(yaml_path_dir)):
        os.remove(os.path.join(yaml_path_dir, result_filename))

    ### Create simulation in DataBase
    datenow = datetime.today()
    sim_data = {'model_name'        : data['model_name'],
                'model_filename'    : model_filename,
                'simulated_duration': sim_duration,
                'username'          : "celinebateaukessler",#TODO
                'internal_date'     : datenow, # used for Mongo sorting but not serializable : Supprimable?
                'date'              : datetime.strftime(datenow, "%Y-%m-%d %H:%M:%S")}
    
    db.simulations.insert_one(sim_data) 
    
    ### Use Mongo ObjectId as simulation name
    simu_name = str(sim_data['_id'])
    
    ### Launch simulation
    ### NB : Don't set shell=True because then it is not possible to interact with the process inside the shell
    
    #socket_id = 'user_name' + simu_name # has to be unique
    #--> TODO replace with DEVS+username+simu_name
    # using the user name as a prefix is a convention on PythonAnywhere

    cmd = ['python2.7', devsimpy_nogui, abs_model_filename, str(sim_duration), '-remote', '-name', simu_name]
    fout = open(simu_name+'.log', 'w+') # where simulation execution report will be written
    ferr = open(simu_name+'.err', 'w+')
    process = subprocess.Popen(cmd, stdout=fout, stderr=ferr, close_fds=True)
    # Call to Popen is non-blocking, BUT, the child process inherits the file descriptors from the parent,
    # and that will include the web app connection to the WSGI server,
    # so the process needs to run and finish before the connection is released and the server notices that the request is finished.
    # This is solved by passing close_fds=True to Popen

    # Store process for process_pause/process_resume/kill operations
    global_running_sim[simu_name] = process
    
    # Additional information on simulation
    #sim_data['output_filename'] = simu_name+'.out'
    #sim_data['log_filename']    = simu_name+'.log'
    #sim_data['socket_id']       = socket_id
    sim_data['pid']             = process.pid
    sim_data['status']          = 'RUNNING'
    sim_data['exit_code']       = 0
            
    # Record all simulation data in DB
    db.simulations.replace_one({'_id': objectid.ObjectId(simu_name)}, sim_data)
    
    return {'success': True, 
            'simulation_name' : simu_name, 
            'info' : db.simulations.find_one({'_id': objectid.ObjectId(simu_name)},
                                             projection={'_id': False, 'internal_date':False})}

#   Simulation representation
############################################################################
@route('/simulations/<simu_name>', method=['OPTIONS','GET'])
@enable_cors
def simulation_report(simu_name):

    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name': simu_name, 'info':status}

    return {'success' : True,
            'simulation_name': simu_name, 
            'info': db.simulations.find_one({'_id': objectid.ObjectId(simu_name)}, 
                                            projection={'_id': False, 'internal_date':False})}


#   Simulation deletion
############################################################################
@route('/simulations/<simu_name>', method=['OPTIONS','DELETE'])
@enable_cors
def delete_simulation(simu_name):
    status = update_status(simu_name)
    
    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name': simu_name, 'info':status}
        
    if status != 'FINISHED':
        global_running_sim[simu_name].send_signal(signal.SIGKILL)
        
    simu = db.simulations.find_one({'_id': objectid.ObjectId(simu_name)})
    if os.path.exists(simu_name + '.report'):
        os.remove(simu_name + '.report')
    if os.path.exists(simu_name + '.log'):
        os.remove(simu_name + '.log')
    # TODO remove also generated result files when well managed...
    db.simulations.delete_one({'_id': objectid.ObjectId(simu_name)})
    
       
    return {'success':True, 'simulation_name':simu_name}

    
#    Simulation pause / resume :
#    suspends / resumes the simulation thread but not the wrapping process
#    (to be called before parameters modification)
############################################################################

@route('/simulations/<simu_name>/pause', method=['OPTIONS','PUT'])
@enable_cors
def pause(simu_name):
    """
    """
    return pause_or_resume (simu_name, 'PAUSE')


@route('/simulations/<simu_name>/resume', method=['OPTIONS','PUT'])
@enable_cors
def resume(simu_name):
    """
    """
    return pause_or_resume (simu_name, 'RESUME')

#   Simulation kill
############################################################################
@route('/simulations/<simu_name>/kill', method=['OPTIONS','PUT'])
@enable_cors
def kill(simu_name):
    """
    """
    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name':simu_name, 'info':status}
    if status == 'FINISHED':
        return {'success':True, 'simulation_name':simu_name, 'info':status}

    global_running_sim[simu_name].send_signal(signal.SIGKILL)
    
    return {'success':True, 'simulation_name':simu_name, 'info':"KILLED"}

###    Simulation process pause (TBC)
############################################################################

@route('/simulations/<simu_name>/process_pause', method=['OPTIONS','PUT'])
@enable_cors
def process_pause(simu_name):
    """
    """
    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name':simu_name, 'info':status}
    if status == 'FINISHED':
        return {'success':False, 'simulation_name':simu_name, 'info':status}

    global_running_sim[simu_name].send_signal(signal.SIGSTOP)
    
    db.simulations.update_one({'_id' : objectid.ObjectId(simu_name)},
                              {'$set':{'status' : "PROCESS_PAUSE"}})
    
    return {'success':True, 'simulation_name':simu_name, 'status':"PROCESS_PAUSED"}


###    Simulation process resume (TBC)
############################################################################

@route('/simulations/<simu_name>/process_resume', method=['OPTIONS','OPTIONS', 'GET'])
@enable_cors
def process_resume(simu_name):
    """
    """
    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name':simu_name, 'info':status}
    if status == 'FINISHED':
        return {'success':False, 'simulation_name':simu_name, 'info':status}

    global_running_sim[simu_name].send_signal(signal.SIGCONT)
    
    db.simulations.update_one({'_id' : objectid.ObjectId(simu_name)},
                              {'$set':{'status' : "RUNNING"}})
    
    return {'success':True, 'simulation_name':simu_name, 'info':"PROCESS_RESUMED"}


############################################################################
#    RESOURCE = SIMULATION --> PARAMETERS
############################################################################
#    Update parameters of 1 block
#    body example :
### example POST body : {"modelID":"A2", "paramName":"maxValue", "paramValue":"50"}
############################################################################

@route('/simulations/<simu_name>/atomics/<block_label>/params', method=['OPTIONS','PUT'])
@enable_cors
def modify(simu_name, block_label):
    """
    """
    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name':simu_name, 'info':status}
    if status != "PAUSED":
        return {'success':False, 'simulation_name':simu_name, 'info':status}

    data = {'block_label': block_label, 'block' : request.json}
    
    simu_response = send_via_socket(simu_name, json.dumps(data))
    
    return {'success'        : ('OK' in simu_response['status']),
            'simulation_name': simu_name, 
            'block_label'    : block_label,
            'status'         : simu_response}


@route('/simulations/<simu_name>/outputs', method=['OPTIONS','GET'])
@enable_cors
def get_simu_outputs(simu_name):
    """
    """
    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name':simu_name, 'info':status}
    if status == "FINISHED":
        return {'success':False, 'simulation_name':simu_name, 'info':status}
    
    simu_response = send_via_socket(simu_name, 'OUTPUTS')
    
    if simu_response['status'] == 'SOCKET_ERROR': 
        return {'success':False, 'simulation_name':simu_name, 'info':'SOCKET_ERROR'}

    return {'success'        : True, 
            'simulation_name': simu_name, 
            'outputs'        : simu_response['outputs']}


############################################################################
#   RESOURCE = SIMULATION RESULTS
############################################################################
#   Simulation report : includes results collection
############################################################################

@route('/simulations/<simu_name>/results', method=['OPTIONS','GET'])
@enable_cors
def simulation_results(simu_name):

    status = update_status(simu_name)

    if status != 'FINISHED':
        return {'success':False, 'simulation_name' : simu_name, 'info': status}

    return {'success'         : True,
            'simulation_name' : simu_name,
            'results'         : db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})['report']}


#   Simulation result as a (time, value) table
############################################################################
@route('/simulations/<simu_name>/results/<result_filename>', method=['OPTIONS','GET'])
@enable_cors
def simulation_time_value_result(simu_name, result_filename):
    """
    """
    status = update_status(simu_name)

    if status != 'FINISHED':
        return {'success':False, 'simulation_name' : simu_name, 'info': status }

    # Build the diagram data as :
    # - 1 list of labels (X or Time axis) called category TBC : what if time delta are not constant???
    # - 1 list of values (Y or Amplitude axis) called data
    result = []
    # TODO add check on file validity
    with open(os.path.join(yaml_path_dir, result_filename)) as fp:
        for line in fp:
            t,v = line.split(" ")
            result.append({"time":t, "value":v.rstrip('\r\n')})
                
    return {"simulation_name": simu_name,
            "result_filename": result_filename,
            "data": result}             
    
@route('/simulations/<simu_name>/results/<result_filename>/<part>', method=['OPTIONS','GET'])
@enable_cors
def simulation_time_value_result(simu_name, result_filename, part):
    """
    """
    status = update_status(simu_name)

    if status != 'FINISHED':
        return {'success':False, 'simulation_name' : simu_name, 'info': status }

    # Build the diagram data as :
    # - 1 list of labels (X or Time axis) called category TBC : what if time delta are not constant???
    # - 1 list of values (Y or Amplitude axis) called data
    result = []
    # TODO add check on file validity
    first = int(part) * 1000 + 1
    last  = first + 1000
    count = 0
    is_last_part = True
    with open(os.path.join(yaml_path_dir, result_filename)) as fp:
        for line in fp:
            count +=1
            if (count >= first) and (count <= last):
                t,v = line.split(" ")
                result.append({"time":t, "value":v.rstrip('\r\n')})
            if count > last:
                is_last_part = False
                break;
                
    return {"simulation_name": simu_name,
            "result_filename": result_filename,
            "part":part,
            "is_last_part":is_last_part,
            "data": result}             
    

#   Simulation logs
############################################################################
@route('/simulations/<simu_name>/log', method=['OPTIONS','GET'])
@enable_cors
def simulation_logs(simu_name):

    status = update_status(simu_name)

    if status == 'UNKNOWN':
        return {'success':False, 'simulation_name' : simu_name, 'info': status}

    simu = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
    with open(simu_name+'.log', 'r') as flog:
        simu['log'] = flog.read()
    db.simulations.update_one({'_id' : objectid.ObjectId(simu_name)}, 
                              {'$set' : {'log' : simu['log']}})
           
    return {'success'         : True, 
            'simulation_name' : simu_name,
            'log'             : simu['log']}


############################################################################
#
#     Application definition
#
############################################################################
debug(True)
application = default_app()

mongoConnection = MongoClient()
db = mongoConnection['DEVSimPy_DB']

if __name__ == "__main__":
    from paste import httpserver
    httpserver.serve(application, host=url_server, port=port_server)
