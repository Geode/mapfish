# 
# Copyright (c) 2008-2011 Camptocamp.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of Camptocamp nor the names of its contributors may 
#    be used to endorse or promote products derived from this software 
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

"""Paster Commands, for use with paster in your MapFish project

The command(s) listed here are for use with Paste to enable easy creation of
various MapFish files.

Currently available commands:

    mf-controller, mf-model
"""

import os
import sys
from ConfigParser import ConfigParser, NoOptionError

from paste.script.command import Command, BadCommand
from paste.script.filemaker import FileOp
from tempita import paste_script_template_renderer

import pylons.util as util

__all__ = ['MapFishControllerCommand', 'MapFishModelCommand', 'MapFishLayerCommand']

def can_import(name):
    """Attempt to __import__ the specified package/module, returning True when
    succeeding, otherwise False"""
    try:
        __import__(name)
        return True
    except ImportError:
        return False

def validateName(name):
    """Validate that the name for the layer isn't present on the
    path already"""
    if not name:
        # This happens when the name is an existing directory
        raise BadCommand('Please give the name of a layer.')
    # 'setup' is a valid controller name, but when paster controller is ran
    # from the root directory of a project, importing setup will import the
    # project's setup.py causing a sys.exit(). Blame relative imports
    if name != 'setup' and can_import(name):
        raise BadCommand(
            "\n\nA module named '%s' is already present in your "
            "PYTHON_PATH.\nChoosing a conflicting name will likely cause "
            "import problems in\nyour controller at some point. It's "
            "suggested that you choose an\nalternate name, and if you'd "
            "like that name to be accessible as\n'%s', add a route "
            "to your projects config/routing.py file similar\nto:\n"
            "    map.connect('%s', controller='my_%s')" \
            % (name, name, name, name))
    return True


class MapFishControllerCommand(Command):
    """Create a MapFish controller and accompanying functional test

    The MapFishController command will create the standard controller template
    file and associated functional test.

    Example usage::

        yourproj% paster mf-controller foos
        Creating yourproj/yourproj/controllers/foos.py
        Creating yourproj/yourproj/tests/functional/test_foos.py

    If you'd like to have controllers underneath a directory, just include
    the path as the controller name and the necessary directories will be
    created for you::

        yourproj% paster mf-controller admin/foos
        Creating yourproj/controllers/admin
        Creating yourproj/yourproj/controllers/admin/foos.py
        Creating yourproj/yourproj/tests/functional/test_admin_foos.py
    """
    summary = __doc__.splitlines()[0]
    usage = '\n' + __doc__

    min_args = 1
    max_args = 1
    group_name = 'mapfish'

    default_verbosity = 3

    parser = Command.standard_parser(simulate=True)
    parser.add_option('--no-test',
                      action='store_true',
                      dest='no_test',
                      help="Don't create the test; just the controller")

    def command(self):
        """Main command to create a mapfish controller"""
        try:
            # read layers.ini
            config = ConfigParser()
            config.read(['layers.ini'])
            # check passed layer is in layers.ini
            sectionName = self.args[0]
            if not config.has_section(sectionName):
                raise BadCommand(
                    'There is no layer section named %s in layers.ini' % \
                    sectionName)

            # get layer parameters
            singular = config.get(sectionName, 'singular')
            plural = config.get(sectionName, 'plural')
            epsg = config.get(sectionName, 'epsg')

            fileOp = FileOp(source_dir=os.path.join(
                os.path.dirname(__file__), 'templates'))
            try:
                singularName, singularDirectory = \
                    fileOp.parse_path_name_args(singular)
                pluralName, pluralDirectory = \
                    fileOp.parse_path_name_args(plural)
            except Exception, e:
                raise BadCommand('No egg_info directory was found')

            # check the name isn't the same as the package
            basePkg = fileOp.find_dir('controllers', True)[0]
            if basePkg.lower() == pluralName.lower():
                raise BadCommand(
                    'Your controller name should not be the same as '
                    'the package name %s' % basePkg)

            # validate the name
            name = pluralName.replace('-', '_')
            validateName(name)

            # set test file name
            fullName = os.path.join(pluralDirectory, name)
            if not fullName.startswith(os.sep):
                fullName = os.sep + fullName
            testName = fullName.replace(os.sep, '_')[1:]

            # set template vars
            modName = name
            fullModName = os.path.join(pluralDirectory, name)
            contrClass = util.class_name_from_module_name(name)
            modelClass = util.class_name_from_module_name(singularName)

            # setup the controller
            fileOp.template_vars.update(
                {'modName': modName,
                 'fullModName': fullModName,
                 'singularName': singularName,
                 'pluralName': pluralName,
                 'contrClass': contrClass,
                 'modelClass': modelClass,
                 'basePkg': basePkg})
            fileOp.copy_file(template='controller.py_tmpl',
                         dest=os.path.join('controllers', pluralDirectory),
                         filename=name,
                         template_renderer=paste_script_template_renderer)
            if not self.options.no_test:
                fileOp.copy_file(template='test_controller.py_tmpl',
                             dest=os.path.join('tests', 'functional'),
                             filename='test_' + testName,
                             template_renderer=paste_script_template_renderer)
            
            resource_command = ("\nTo create the appropriate RESTful mapping, "
                                "add a map statement to your\n")
            resource_command += ("config/routing.py file in the CUSTOM ROUTES section "
                                 "like this:\n\n") 
            resource_command += ('map.connect("/%s/count", controller="%s", '
                                 'action="count")\n' % (pluralName, pluralName))
            resource_command += 'map.resource("%s", "%s")\n' % \
                    (singularName, pluralName)

            print resource_command

        except BadCommand, e:
            raise BadCommand('An error occurred. %s' % e)
        except:
            msg = str(sys.exc_info()[1])
            raise BadCommand('An unknown error occurred. %s' % msg)

class MapFishModelCommand(Command):
    """Create a MapFish model

    The MapFishModel command will create the standard model template file.

    Example usage::

        yourproj% paster mf-model foos
        Creating yourproj/yourproj/model/foos.py

    If you'd like to have models underneath a directory, just include
    the path as the model name and the necessary directories will be
    created for you::

        yourproj% paster mf-model admin/foos
        Creating yourproj/model/admin
        Creating yourproj/yourproj/model/admin/foos.py
    """
    summary = __doc__.splitlines()[0]
    usage = '\n' + __doc__

    min_args = 1
    max_args = 1
    group_name = 'mapfish'

    default_verbosity = 3

    parser = Command.standard_parser(simulate=True)

    def command(self):
        """Main command to create mapfish model"""
        try:
            # read layers.ini
            config = ConfigParser()
            config.read(['layers.ini'])
            # check passed layer is in layers.ini
            sectionName = self.args[0]
            if not config.has_section(sectionName):
                raise BadCommand(
                    'There is no layer section named %s in layers.ini' % \
                    sectionName)

            # get layer parameters
            singular = config.get(sectionName, 'singular')
            plural = config.get(sectionName, 'plural')
            table = config.get(sectionName, 'table')
            epsg = config.get(sectionName, 'epsg')
            geomColName = config.get(sectionName, 'geomcolumn')
            if config.has_option(sectionName, 'schema'):
                schema = config.get(sectionName, 'schema')
            else:
                schema = None

            # get geometry type
            if not config.has_option(sectionName, 'geomtype'):
                geomtype = 'Geometry'
            else:
                raw_geomtype = config.get(sectionName, 'geomtype')
                # check if the value is valid (geometries supported by GeoAlchemy)
                valid_types = ['Geometry', 'Point', 'Curve', 'LineString', 'Polygon',
                                'MultiPoint', 'MultiLineString', 'MultiPolygon', 'GeometryCollection']
                
                if raw_geomtype in valid_types:
                    geomtype = raw_geomtype
                else:
                    raise BadCommand('Geometry type "%s" is unknown, valid values are: %s' 
                                        % (raw_geomtype, valid_types))

            fileOp = FileOp(source_dir=os.path.join(
                os.path.dirname(__file__), 'templates'))
            try:
                singularName, singularDirectory = \
                    fileOp.parse_path_name_args(singular)
                pluralName, pluralDirectory = \
                    fileOp.parse_path_name_args(plural)
            except:
                raise BadCommand('No egg_info directory was found')

            # check the name isn't the same as the package
            basePkg = fileOp.find_dir('model', True)[0]
            if basePkg.lower() == pluralName.lower():
                raise BadCommand(
                    'Your model name should not be the same as '
                    'the package name %s' % basePkg)

            # validate the name
            name = pluralName.replace('-', '_')
            validateName(name)

            # set template vars
            modelClass = util.class_name_from_module_name(singularName)

            # setup the model
            fileOp.template_vars.update(
                {'modelClass': modelClass,
                 'table': table,
                 'epsg': epsg,
                 'geomColName': geomColName,
                 'geomType': geomtype,
                 'basePkg': basePkg,
                 'schema': schema})
            fileOp.copy_file(template='model.py_tmpl',
                         dest=os.path.join('model', pluralDirectory),
                         filename=name,
                         template_renderer=paste_script_template_renderer)

        except BadCommand, e:
            raise BadCommand('An error occurred. %s' % e)
        except:
            msg = str(sys.exc_info()[1])
            raise BadCommand('An unknown error occurred. %s' % msg)

class MapFishLayerCommand(Command):
    """Create a MapFish layer (controller + model).

    The MapFishLayer command will create the standard controller and model
    template files. It combines the MapFishController and MapFishModel
    commands.

    Example usage::

        yourproj% paster mf-layer foos
        Creating yourproj/yourproj/controllers/foos.py
        Creating yourproj/yourproj/tests/functional/test_foos.py
        Creating yourproj/yourproj/model/foos.py

    If you'd like to have controllers and models underneath a directory, just
    include the path as the controller name and the necessary directories will
    be created for you::

        yourproj% paster mf-layer admin/foos
        Creating yourproj/controllers/admin
        Creating yourproj/yourproj/controllers/admin/foos.py
        Creating yourproj/yourproj/tests/functional/test_admin_foos.py
        Creating yourproj/model/admin
        Creating yourproj/yourproj/model/admin/foos.py
    """
    summary = __doc__.splitlines()[0]
    usage = '\n' + __doc__

    min_args = 1
    max_args = 1
    group_name = 'mapfish'

    default_verbosity = 3

    parser = Command.standard_parser(simulate=True)
    parser.add_option('--no-test',
                      action='store_true',
                      dest='no_test',
                      help="Don't create the test; just the controller")

    def run(self, args):
        try:
            contrCmd = MapFishControllerCommand('mf-controller')
            contrCmd.run(args)
            modelCmd = MapFishModelCommand('mf-model')
            modelCmd.run(args)
        except BadCommand, e:
            raise BadCommand('An error occurred. %s' % e)
        except:
            msg = str(sys.exc_info()[1])
            raise BadCommand('An unknown error occurred. %s' % msg)
