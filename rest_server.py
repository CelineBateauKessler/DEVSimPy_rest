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

import __builtin__
from compiler.pyassem import Block

#import BaseDEVS, DomainBehavior, DomainStructure

__builtin__.__dict__['DEVS_DIR_PATH_DICT'] = {}

from param import * 

### global variables
global_running_sim = {} 

BLOCK_FILE_EXTENSIONS = ['.amd', '.cmd', '.py']

# the decorator
def enable_cors(fn):
    def _enable_cors(*args, **kwargs):
        # set CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

        if request.method != 'OPTIONS':
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
    for entry in os.listdir(yaml_path_dir):
        
        if entry.endswith('.yaml'):
            model_name = entry.split('.')[0]
            filename = os.path.join(yaml_path_dir, entry)
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

@route('/models', method=['GET'])
@enable_cors
def models_list():
    """ Return the list of the models available on the server
        with filename, date and size
    """
    list = getYAMLFilenames()

    return {'models' : list}

#   Model creation
############################################################################
@route('/models', method=['POST'])
@enable_cors
def create_model():
    
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext != '.yaml':
        return {'success' : False, 'info': 'Only .yaml file allowed.'}
    
    if os.path.exists(os.path.join(yaml_path_dir, name+ext)):
        return {'success' : False , 'info' : 'File already exists'}
    
    upload.save(yaml_path_dir, overwrite=False) # appends upload.filename automatically
    #os.chmod(os.path.join(yaml_path_dir, (name + ext)), stat.S_IWGRP)
    # TODO add a check on the yaml file
    return {'success' : True, 'model_name':name}
    #except:
    #    import traceback
    #    return {'success' : False , 'info' : traceback.format_exc()}

    
#   Model update
############################################################################
@route('/models/<model_name>', method=['POST'])
@enable_cors
def update_model(model_name):
    
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext != '.yaml':
        return {'success' : False, 'info': 'Only .yaml file allowed.'}
    if name != model_name: 
        return {'success' : False, 'info': 'Filename does not match model_name.'}
    upload.save(yaml_path_dir, overwrite=True) # appends upload.filename automatically
    # TODO add a check on the yaml file
    return {'success' : True, 'model_name':name}
    

#   Model deletion
############################################################################
@route('/models/<model_name>', method=['DELETE'])
@enable_cors
def model_delete(model_name):

    model_abs_filename = os.path.join(yaml_path_dir, model_name+'.yaml')
    
    if os.path.exists(model_abs_filename):
        os.remove(model_abs_filename)
    
    return {'success' : True}
    

#   Model representation
############################################################################

@route('/models/<model_name>', method=['GET'])
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
                "model"      : data} 
                #"model"      : json.loads(data) }
    elif request.headers['Accept'] == 'text/x-yaml':
        data = getYAMLFile(model_filename)
        return {"success"    : data!={} and data!=[],
                "model_name" :model_name, 
                "model"      : data }
    else:
        return {"success":False, "info":"unexpected Accept type = " + request.headers['Accept']}

    
############################################################################
#    RESOURCE = ATOMIC MODEL CODE
############################################################################
#   Blocks collection : no need for a global list of available blocks yet
############################################################################

#   Block creation
############################################################################
@route('/codeblocks', method=['POST'])
@enable_cors
def create_codeblock():
    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext not in BLOCK_FILE_EXTENSIONS:
        return {'success' : False, 'info': 'Only .amd, .cmd and .py files allowed.'}
    
    if os.path.exists(os.path.join(block_path_dir, name+ext)):
        return {'success' : False , 'info' : 'File already exists'}
    
    upload.save(block_path_dir, overwrite=False) # appends upload.filename automatically
    # TODO add a check on file validity
    return {'success' : True, 'block_name':name}

    
#   Block update
############################################################################
@route('/codeblocks/<block_name>', method=['POST'])
@enable_cors
def update_codeblock(block_name):

    upload    = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext not in BLOCK_FILE_EXTENSIONS:
        return {'success' : False, 'info': 'Only .amd, .cmd and .py files allowed.'}
    if name != block_name: 
        return {'success' : False, 'info': 'Filename does not match block_name.'}

    upload.save(block_path_dir, overwrite=True) # appends upload.filename automatically
    # TODO add a check on file validity
    return {'success' : True, 'block_name':name}


#   Block deletion
############################################################################
@route('/codeblocks/<block_name>', method=['DELETE'])
@enable_cors
def delete_codeblock(block_name):
    block_abs_filename = os.path.join(block_path_dir, block_name)
    
    for ext in BLOCK_FILE_EXTENSIONS:
        if os.path.exists(block_abs_filename + ext):
            os.remove(block_abs_filename + ext)
    
    return {'success' : True}


#   Blocks collection within a model
############################################################################
@route('/models/<model_name>/atomics', method=['GET'])
@enable_cors
def model_atomicblocks_list(model_name):
    """ get the model blocks list from yaml
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, os.path.join(yaml_path_dir, model_name + '.yaml'), "-blockslist"]
    output = subprocess.check_output(cmd)

    return {'success':True, 'blocks':json.loads(output)}


#   Block parameters (for a given model)
############################################################################
@route('/models/<model_name>/atomics/<block_label>/params', method=['GET'])
@enable_cors
def model_atomicblock_parameters(model_name, block_label):
    """ get the parameters of the block
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, os.path.join(yaml_path_dir, model_name + '.yaml'), "-blockargs", block_label]
    output = subprocess.check_output(cmd)

    return {'success':True, 'block':json.loads(output)}


#   Block parameters update (for a given model)
#   body example : {"maxStep":1, "maxValue":100, "minStep":1, "minValue":0, "start":0}
############################################################################
@route('/models/<model_name>/atomics/<block_label>/params', method=['PUT'])
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
    return {'success':True, 'block':json.loads(output)}


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
        return "UNKNOWN " + simu_name

    if 'FINISHED' not in simu['status']:
        try:
            # check on process status
            simu_process = global_running_sim[simu_name]
            simu_process.poll()
            returncode = simu_process.returncode
        
            # test if process is finished <=> (returnCode != None)
            if (returncode != None):
                # update status
                simu['status'] = "FINISHED with exit code " + str(returncode)
                
                del global_running_sim[simu_name]
            
                with open(simu['output_filename'], 'r') as fout:
                    report = fout.read()
                    try:
                        json_report = json.loads(report)
                        #del json_report['log']
                        simu['report'] = json_report
                    except:
                        simu['report'] = report
                
                with open(simu['log_filename'], 'r') as flog:
                    simu['log'] = flog.read()   
                
        except:
            # Simulation is marked as RUNNING but process cannot be found
            # might happen in case of server reboot...
            simu['status'] = "UNEXPECTED_END"
        
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
                        'status'          : thread_status, 
                        'simulation_time' : thread_json_response['simulation_time']}
            else:
                return {'success' : False, 
                        'status'  : thread_status, 
                        'expected': CONVERT[action]['expected_thread_status']}
        except:
            raise
            return {'success': False, 'status': thread_response}
            
    else: 
        return {'success':False, 'status': current_status} 

def send_via_socket(simu_name, data):
    """ send data string to the simulation identified by simu_name
    """
    try:
        simu = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
        socket_address = '\0' + simu['socket_id']
        comm_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        #socket_address = ('localhost', 5555)
        #comm_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        comm_socket.connect((socket_address))
        comm_socket.sendall(data)
        status = comm_socket.recv(1024)
        json_status = json.loads(status)
        comm_socket.close()
    except:
        json_status = {'status' : "SOCKET_ERROR"}
        comm_socket.close()
        #raise 

    return json_status


#    Simulations collection
############################################################################
@route('/simulations', method=['GET'])
@enable_cors
def simulations_list():
    """
    """
    simu_list = {}
        
    cursor = db.simulations.find().sort([("internal_date", pymongo.ASCENDING)])
    # possibility to add a filter on the username
    
    for simu in cursor:
        simu_name = str(simu['_id'])
        simu_list[simu_name] = simu
        
        if 'FINISHED' not in simu['status']: 
            update_status(simu_name)
            simu_list[simu_name] = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
            
        # Handle Mongo non serializable fields TBC
        del simu_list[simu_name]['_id'] 
        del simu_list[simu_name]['internal_date']
    
    return simu_list


#    Simulation creation
#    body example :  {"model_filename":"test.yaml", "simulated_duration":"50"}
############################################################################
@route('/simulations', method=['POST'])
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
    socket_id = "celinebateaukessler."+simu_name # has to be unique
    #--> TODO replace with DEVS+username+simu_name
    # using the user name as a prefix is a convention on PythonAnywhere

    cmd = ['python2.7', devsimpy_nogui, abs_model_filename, str(sim_duration), socket_id]
    fout = open(simu_name+'.out', 'w+') # where simulation execution report will be written
    flog = open(simu_name+'.log', 'w+') # where simulation execution report will be written
    process = subprocess.Popen(cmd, stdout=fout, stderr=flog, close_fds=True)
    # Call to Popen is non-blocking, BUT, the child process inherits the file descriptors from the parent,
    # and that will include the web app connection to the WSGI server,
    # so the process needs to run and finish before the connection is released and the server notices that the request is finished.
    # This is solved by passing close_fds=True to Popen

    # Store process for process_pause/process_resume/kill operations
    global_running_sim[simu_name] = process
    
    # Additional information on simulation
    sim_data['output_filename'] = simu_name+'.out'
    sim_data['log_filename']    = simu_name+'.log'
    sim_data['socket_id']       = socket_id
    sim_data['pid']             = process.pid
    sim_data['status']          = 'RUNNING'
    
    db.simulations.replace_one({'_id': objectid.ObjectId(simu_name)}, sim_data)
    
    return {'success': True, 
            'simulation' : {'simulation_name' : simu_name, 
                            'simulation_data' : db.simulations.find_one({'_id': objectid.ObjectId(simu_name)}, 
                                                                        projection={'_id': False, 'internal_date':False})
                            }
            }    


#   Simulation representation
############################################################################
@route('/simulations/<simu_name>', method=['GET'])
@enable_cors
def simulation_report(simu_name):

    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}

    return {'simulation_name': simu_name, 
            'info': db.simulations.find_one({'_id': objectid.ObjectId(simu_name)}, 
                                            projection={'_id': False, 'internal_date':False})}


#    Simulation pause / resume :
#    suspends / resumes the simulation thread but not the wrapping process
#    (to be called before parameters modification)
############################################################################

@route('/simulations/<simu_name>/pause', method=['PUT'])
@enable_cors
def pause(simu_name):
    """
    """
    return pause_or_resume (simu_name, 'PAUSE')


@route('/simulations/<simu_name>/resume', method=['PUT'])
@enable_cors
def resume(simu_name):
    """
    """
    return pause_or_resume (simu_name, 'RESUME')

#   Simulation kill
############################################################################
@route('/simulations/<simu_name>/kill', method=['PUT'])
@enable_cors
def kill(simu_name):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' in status:
        return {'success':True, 'info':status}

    global_running_sim[simu_name].send_signal(signal.SIGKILL)
    
    return {'success':True, 'info':"KILLED"}

###    Simulation process pause (TBC)
############################################################################

@route('/simulations/<simu_name>/process_pause', method=['PUT'])
@enable_cors
def process_pause(simu_name):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' in status:
        return {'success':False, 'info':status}

    global_running_sim[simu_name].send_signal(signal.SIGSTOP)
    
    db.simulations.upadte_one({'_id' : objectid.ObjectId(simu_name)},
                              {'$set':{'status' : "PROCESS_PAUSE"}})
    
    return {'success':True, 'status':"PROCESS_PAUSED"}


###    Simulation process resume (TBC)
############################################################################

@route('/simulations/<simu_name>/process_resume', method=['OPTIONS', 'GET'])
@enable_cors
def process_resume(simu_name):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' in status:
        return {'success':False, 'info':status}

    global_running_sim[simu_name].send_signal(signal.SIGCONT)
    
    db.simulations.upadte_one({'_id' : objectid.ObjectId(simu_name)},
                              {'$set':{'status' : "RUNNING"}})
    
    return {'success':True, 'info':"PROCESS_RESUMED"}


############################################################################
#    RESOURCE = SIMULATION --> PARAMETERS
############################################################################
#    Update parameters of 1 block
#    body example :
### example POST body : {"modelID":"A2", "paramName":"maxValue", "paramValue":"50"}
############################################################################

@route('/simulations/<simu_name>/atomics/<block_label>/params', method=['PUT'])
@enable_cors
def modify(simu_name, block_label):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if status != "PAUSED":
        return {'success':False, 'info':status}

    data = {'block_label': block_label, 'block' : request.json}
    
    simu_response = send_via_socket(simu_name, json.dumps(data))
    
    simu_response['success'] = ('OK' in simu_response['status'])
    
    return simu_response


############################################################################
#   RESOURCE = SIMULATION RESULTS
############################################################################
#   Simulation report : includes results collection
############################################################################

@route('/simulations/<simu_name>/results', method=['GET'])
@enable_cors
def simulation_results(simu_name):

    status = update_status(simu_name)

    if 'FINISHED' not in status:
        return {'success':False, 'simulation_name' : simu_name, 'info': {'status' : status}}

    return {'success'         :True,
            'simulation_name' : simu_name,
            'results'         : db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})['report']}


#   Simulation result as a (time, value) table
############################################################################
@route('/simulations/<simu_name>/results/<result_filename>', method=['GET'])
@enable_cors
def simulation_time_value_result(simu_name, result_filename):
    """
    """
    status = update_status(simu_name)

    if 'FINISHED' not in status:
        return {'success':False, 'simulation_name' : simu_name, 'info': {'status' : status}}

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

#   Simulation logs
############################################################################
@route('/simulations/<simu_name>/log', method=['GET'])
@enable_cors
def simulation_logs(simu_name):

    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'simulation_name' : simu_name, 'info': {'status' : status}}

    simu = db.simulations.find_one({'_id' : objectid.ObjectId(simu_name)})
    with open(simu['log_filename'], 'r') as flog:
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
