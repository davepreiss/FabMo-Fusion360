import http.client
import json
import io, codecs, mimetypes, sys, uuid
import webbrowser
AP_ADDRESS = '192.168.42.1'
AP_PORT = 80
TIMEOUT = 3
def find_tools(debug=False):
    '''
    Retreive a list of tools on the network by querying the FabMo Tool Minder on localhost.
    Must have a tool minder installed and running for this to work.
    https://github.com/FabMo/FabMo-Tool-Minder-Desktop
    '''
    if(debug):
        return [FabMoTool('demo.gofabmo.org', 80, hostname='demo.gofabmo.org')]

    exc = None
    tools = []
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=TIMEOUT)
        conn.request('GET', '/where_is_my_tool')
        response = conn.getresponse()
        tools = json.loads(response.read().decode('utf-8'))
        conn.close()
    except ConnectionRefusedError as e:
        exc = ConnectionRefusedError('Could not find any tools on the network.  The FabMo Tool Minder service does not appear to be running.')
    except Exception as e:
        exc = Exception('Could not find any tools on the network: ' + str(e))

    ap_tools = []
    if exc or not tools:
        try:
            conn = http.client.HTTPConnection(AP_ADDRESS, AP_PORT,timeout=TIMEOUT)
            conn.request('GET', '/status')
            response = conn.getresponse()
            conn.close()
            ap_tools.append(FabMoTool(AP_ADDRESS, AP_PORT))
        except Exception as e:
            pass


    return ap_tools + [FabMoTool.make(tool) for tool in tools]

class FabMoTool:
    '''
    Represents a specific tool on the network.
    '''

    def __init__(self, ip, port, hostname=''):
        self.ip = ip
        self.port = port
        self.hostname = hostname

    def show_dashboard(self):
        webbrowser.open('http://' + self.ip + ':' + str(self.port) + '/')

    def show_job_manager(self):
        webbrowser.open('http://' + self.ip + ':' + str(self.port) + '/#/app/job-manager')

    def submit_job(self, codes, filename=None, name=None, description=None):
        '''
        Submit a job to the tool's job queue.
        codes is a string containing G-Code or OpenSBP code
        filename should correspond to the type of code submitted, ending with .nc or .g for g-code and .sbp for opensbp code
        name should be a short descriptive name of the job
        description can be a longer description of the job, perhaps describing the conditions of the design input
        '''
        filename = filename or 'job.nc'
        name = name or filename
        description = description or ''

        # Metadata request
        # POSTs job-level information (the names and descriptions of all files for the upload)
        # (For now, we're only posting one file)
        conn = http.client.HTTPConnection(self.ip, self.port)
        headers = {"Content-type":"application/json", "Accept":"text/plain"}
        metadata = {
            'files' : [
                {
                    'filename' :filename,
                    'name' : name,
                    'description' : description}
            ],
            'meta' : {}
        }
        json_payload = json.dumps(metadata)
        conn.request("POST", "/job", json_payload, headers)
        response = conn.getresponse()
        response_text = response.read().decode('utf-8')
        response_data = json.loads(response_text)['data']

        # Payload request
        # POSTs the actual job content
        content_type, body = MultipartFormdataEncoder().encode([('key', response_data['key']), ('index',0)], [('file', filename, io.BytesIO(codes.encode('utf-8')))])
        headers = {"Content-type":content_type, "Accept":"text/plain"}
        conn.request("POST", "/job", body, headers)
        response = conn.getresponse()
        response_text = response.read().decode('utf-8')
        response_data = json.loads(response_text)
        conn.close()

        # Throw an exception if the server rejected our request
        if(response_data['status']) != 'success':
            raise Exception(response_data['message'])
        return response_data['data']['data']['jobs'][0]

    def get_status(self):
        conn = http.client.HTTPConnection(self.ip, self.port)
        try:
            conn.request("GET", "/status", '', {})
            response = conn.getresponse()
            response_text = response.read().decode('utf-8')
            response_data = json.loads(response_text)
            if response_data['status'] == 'error':
                raise Exception(response_data['message'])
        finally:
            conn.close()
        return response_data['data']['status']


    @classmethod
    def make(cls, obj):
        return FabMoTool(obj['network'][0]['ip_address'], obj['server_port'], obj['hostname'])



class MultipartFormdataEncoder(object):
    def __init__(self):
        self.boundary = uuid.uuid4().hex
        self.content_type = 'multipart/form-data; boundary={}'.format(self.boundary)

    @classmethod
    def u(cls, s):
        if sys.hexversion < 0x03000000 and isinstance(s, str):
            s = s.decode('utf-8')
        if sys.hexversion >= 0x03000000 and isinstance(s, bytes):
            s = s.decode('utf-8')
        return s

    def iter(self, fields, files):
        """
        fields is a sequence of (name, value) elements for regular form fields.
        files is a sequence of (name, filename, file-type) elements for data to be uploaded as files
        Yield body's chunk as bytes
        """
        encoder = codecs.getencoder('utf-8')
        for (key, value) in fields:
            key = self.u(key)
            yield encoder('--{}\r\n'.format(self.boundary))
            yield encoder(self.u('Content-Disposition: form-data; name="{}"\r\n').format(key))
            yield encoder('\r\n')
            if isinstance(value, int) or isinstance(value, float):
                value = str(value)
            yield encoder(self.u(value))
            yield encoder('\r\n')
        for (key, filename, fd) in files:
            key = self.u(key)
            filename = self.u(filename)
            yield encoder('--{}\r\n'.format(self.boundary))
            yield encoder(self.u('Content-Disposition: form-data; name="{}"; filename="{}"\r\n').format(key, filename))
            yield encoder('Content-Type: {}\r\n'.format(mimetypes.guess_type(filename)[0] or 'application/octet-stream'))
            yield encoder('\r\n')
            with fd:
                buff = fd.read()
                yield (buff, len(buff))
            yield encoder('\r\n')
        yield encoder('--{}--\r\n'.format(self.boundary))

    def encode(self, fields, files):
        body = io.BytesIO()
        for chunk, chunk_len in self.iter(fields, files):
            body.write(chunk)
        return self.content_type, body.getvalue()

if __name__ == "__main__":
    print(find_tools())
