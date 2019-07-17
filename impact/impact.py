#import numpy as np

from .parsers import parse_impact_input, load_many_fort, FORT_STAT_TYPES, FORT_PARTICLE_TYPES, FORT_SLICE_TYPES, header_str, header_bookkeeper
from . import writers
from .lattice import ele_dict_from
from . import tools
import numpy as np
import tempfile
import shutil
from time import time
import os



class Impact:
    """
    
    Files will be written into a temporary directory within workdir. 
    If workdir=None, a location will be determined by the system. 
    This behavior can
    
    """
    def __init__(self,
                input_file=None, #'ImpactT.in',
                impact_bin='$IMPACTT_BIN',
                workdir=None,
                use_mpi = False,
                mpi_exe = 'mpirun', # If needed
                path = None, # Actual simulation path. If set, will not make a temporary directory. 
                verbose=True):
        
        # Save init
        self.original_input_file = input_file
        self.workdir = workdir
        self.verbose=verbose
        self.impact_bin = impact_bin
        self.mpi_exe = mpi_exe
        self.use_mpi = use_mpi
        self.path = path # Actual working path. 
        
        # These will be set
        self.timeout=None
        self.input = {'header':{}, 'lattice':[]}
        self.output = {}
        self.auto_cleanup = True
        self.ele = {} # Convenience lookup of elements in lattice by name
        
        
        # Run control
        self.finished = False
        self.configured = False
        self.using_tempdir = False
        
        # Call configure
        if input_file:
            self.load_input(input_file)
            self.configure()
        else:
            self.vprint('Warning: Input file does not exist. Not configured. Please set header and lattice.')

    def __del__(self):
        if self.auto_cleanup:
            self.clean() # clean directory before deleting

    def clean(self, override=False):   
        # Only remove temporary directory. Never delete anything else!!!
        if (self.using_tempdir or override) and os.path.exists(self.path):
            self.vprint('deleting: ', self.path)
            shutil.rmtree(self.path)
        else: 
            self.vprint('Warning: no cleanup because path is not a temporary directory:', self.path)
            
    def configure(self):
        self.configure_impact(workdir=self.workdir)
        
    def configure_impact(self, input_filePath=None, workdir=None):
        
        if input_filePath:
            self.load_input(input_filePath)
        
        # Header Bookkeeper
        self.input['header'] = header_bookkeeper(self.input['header'], verbose=self.verbose)
        
        if  len(self.input['lattice']) == 0:
            self.vprint('Warning: lattice is empty. Not configured')
            self.configured = False
            return
        
        

        
        # Set ele dict:
        self.ele = ele_dict_from(self.input['lattice'])
        
        # Temporary directory for path
        if not self.path:
            self.path = os.path.abspath(tempfile.TemporaryDirectory(prefix='temp_impactT_', dir=workdir).name)
            os.mkdir(self.path)
            self.using_tempdir = True
        else:
            self.using_tempdir = False
     
        self.vprint(header_str(self.input['header']))
        self.vprint('Configured to run in:', self.path)
        
        self.configured = True
        
        
    def load_input(self, input_filePath):
        f = tools.full_path(input_filePath)
        self.original_path, _ = os.path.split(f) # Get original path
        self.input = parse_impact_input(f)
    
    def load_output(self):
        self.output['stats'] = load_many_fort(self.path, FORT_STAT_TYPES, verbose=self.verbose)
        self.output['slice_info'] = load_many_fort(self.path, FORT_SLICE_TYPES, verbose=self.verbose)
        
    def load_particles(self):
        self.particles = load_many_fort(self.path, FORT_PARTICLE_TYPES, verbose=self.verbose)   
        
    def run(self):
        if not self.configured:
            self.vprint('not configured to run')
            return
        self.run_impact(verbose=self.verbose, timeout=self.timeout)        
    
    
    def get_run_script(self, write_to_path=True):
        """
        Assembles the run script. Optionally writes a file 'run' with this line to path.
        """
        
        if self.use_mpi:
            n_procs = self.input['header']['Npcol'] * self.input['header']['Nprow']
            runscript = [self.mpi_exe, '-n', str(n_procs), tools.full_path(self.impact_bin)]
        else:
            runscript = [tools.full_path(self.impact_bin)]
            
        if write_to_path:
            with open(os.path.join(self.path, 'run'), 'w') as f:
                f.write(' '.join(runscript))
            
        return runscript

    
    def run_impact(self, verbose=False, timeout=None):
        
        # Check that binary exists
        self.impact_bin = tools.full_path(self.impact_bin)
        assert os.path.exists(self.impact_bin)
        
        run_info = self.output['run_info'] = {}
        t1 = time()
        run_info['start_time'] = t1
        
        init_dir = os.getcwd()
        os.chdir(self.path)
        
        # Write input
        self.write_input()
        
        runscript = self.get_run_script()
        
        try: 
            if timeout:
                res = tools.execute2(runscript, timeout=timeout)
                log = res['log']
                self.error = res['error']
                run_info['error'] = self.error
                run_info['why_run_error'] = res['why_error']
    
            else:
                # Interactive output, for Jupyter
                log = []
                counter = 0
                for path in tools.execute(runscript):
                    # Fancy clearing of old lines
                    counter +=1
                    if verbose:
                        if counter < 15:
                            print(path, end='')
                        else:
                            print('\r', path.strip()+', elapsed: '+str(time()-t1), end='')
                    log.append(path)
                self.vprint('Finished.')
            self.log = log
                            
            # Load output    
            self.load_output()
            self.load_particles()
        except Exception as ex:
            print('Run Aborted', ex)
            run_info['error'] = True
            run_info['why_run_error'] = str(ex)
        finally:
            run_info['run_time'] = time() - t1
            # Return to init_dir
            os.chdir(init_dir)    
 
        self.finished = True
        
    def write_input(self,  input_filename='ImpactT.in'):
        
        path = self.path
        assert os.path.exists(path)
        
        filePath = os.path.join(path, input_filename)
        # Write main input file
        writers.write_impact_input(filePath, self.input['header'], self.input['lattice'])
        
        # Write fieldmaps
        for fmap, data in self.input['fieldmaps'].items():
            file = os.path.join(path, fmap)
            np.savetxt(file, data)
        
        # Input particles (if required)
        # Symlink
        if self.input['header']['Flagdist'] == 16:
            src = self.input['input_particle_file']
            dest = os.path.join(path, 'partcl.data')
            if not os.path.exists(dest):
                writers.write_input_particles_from_file(src, dest, self.input['header']['Np'] )
            else:
                self.vprint('partcl.data already exits, will not overwrite.')
        
            

                
    def set_property(self, property_string, value):
        """
        Convenience syntax to set the header or element property. 
        property_string should be 'header:key' or 'ele_name:key'
        
        Examples of property_string: 'header:Np', 'SOL1:solenoid_field_scale'
        
        """
        name, prop = property_string.split(':')
        if name == 'header':
            self.input['header'][prop] = value
        else:
            self.ele[name][prop] = value
    
        
                
    def archive(self, h5):
        """
        Archive all data to an h5 handle. 
        """
        
        # All input
        writers.write_impact_input_h5(h5, self.input, name='input')

        # All output
        writers.write_impact_output_h5(h5, self.output, name=None) 
            
        # Particles    
        g = h5.create_group('particles')
        for key in self.particles:
            particle_data = self.particles[key]
            name = key
            charge = self.macrocharge() * len(particle_data['x'])
            self.vprint('Archiving', name, 'with charge', charge)
            writers.write_impact_particles_h5(g, particle_data, name=name, total_charge=charge) 
        
    
    def total_charge(self):
        H = self.input['header']
        return H['Bcurr']/H['Bfreq']

    def macrocharge(self):
        H = self.input['header']
        Np = H['Np']
        if Np == 0:
            self.vprint('Error: zero particles. Returning zero macrocharge')
            return 0
        else:
            return H['Bcurr']/H['Bfreq']/Np
        
        
    def fingerprint(self):
        """
        Data fingerprint using the input. 
        """
        return tools.fingerprint(self.input)
                
    def vprint(self, *args):
        # Verbose print
        if self.verbose:
            print(*args)
    
        
    def __str__(self):
        path = self.path
        s = header_str(self.input['header'])
        if self.finished:
            s += 'Impact-T finished in '+path
        elif self.configured:
            s += 'Impact-T configured in '+path
        else:
            s += 'Impact-T not configured.'
        return s
        