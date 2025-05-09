# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import pathlib
import re
import shutil
import subprocess

from gns3.controller import Controller
from gns3.ports.ethernet_port import EthernetPort
from gns3.ports.serial_port import SerialPort
from gns3.utils.bring_to_front import bring_window_to_front_from_process_name, bring_window_to_front_from_title
from gns3.utils.normalize_filename import normalize_filename
from gns3.qt import QtGui, QtCore

from .base_node import BaseNode

import logging
log = logging.getLogger(__name__)


class Node(BaseNode):

    def __init__(self, module, compute, project):

        super().__init__(module, compute, project)

        self._node_id = None
        self._node_directory = None
        self._command_line = None
        self._always_on = False

        # minimum required base settings
        self._settings = {"name": "",
                          "x": None,
                          "y": None,
                          "z": 1,
                          "locked": False}

    def settings(self):
        """
        Returns this node settings.

        :return: settings (dictionary)
        """

        return self._settings

    def setSettingValue(self, key, value):
        """
        Set a setting on this node.

        :param key: setting key
        :param value: setting value
        """

        self._settings[key] = value

    def node_id(self):
        """
        Return the ID of this device

        :returns: identifier (string)
        """

        return self._node_id

    def setName(self, name):
        """
        Set the name for this node.

        :param name: node name
        """

        self._settings["name"] = name

    def name(self):
        """
        Returns the name of this node.

        :returns: name (string)
        """

        return self._settings["name"]

    def usage(self):
        """
        Returns the usage info for this node.

        :returns: usage (string)
        """

        return self._settings.get("usage")

    def nodeDir(self):
        """
        Return the working directory of this node

        :returns: identifier (string)
        """

        return self._node_directory

    def commandLine(self):
        """
        Return the command line used to run this node

        :returns: identifier (string)
        """

        return self._command_line

    def x(self):
        """
        Returns X coordinate

        :returns: integer
        """

        return self._settings["x"]

    def y(self):
        """
        Returns Y coordinate

        :returns: integer
        """

        return self._settings["y"]

    def z(self):
        """
        Returns Z coordinate

        :returns: integer
        """

        return self._settings["z"]

    def locked(self):
        """
        Is the node locked
        """

        return self._settings["locked"]

    def setSymbol(self, symbol):
        """
        Sets the symbol for this node.

        :param symbol: symbol path
        """

        self._settings["symbol"] = symbol

    def symbol(self):
        """
        Returns the symbol for this node.

        :returns: symbol path
        """

        return self._settings["symbol"]

    def console(self):
        """
        Returns the console port number of this node

        :returns: port number
        """

        return self.settings().get("console")

    def isStarted(self):
        """
        :returns: Boolean True if this node is running
        """

        return self.status() == Node.started

    def isAlwaysOn(self):
        """
        Whether the node is always on.

        :returns: boolean
        """

        return self._always_on

    def configFiles(self):
        """
        Name of the configuration files

        This method should be overridden in derived classes

        :returns: List of configuration files, False if no files
        """

        return None

    def configTextFiles(self):
        """
        Name of the configuration files, which are plain text files

        :returns: List of configuration files, False if no files
        """

        return self.configFiles()

    def get(self, path, *args, **kwargs):
        """
        GET on current server / project
        """

        return self.controllerHttpGet("/nodes/{node_id}{path}".format(node_id=self._node_id, path=path), *args, **kwargs)

    def post(self, path, *args, **kwargs):
        """
        POST on current server / project
        """

        return self.controllerHttpPost("/nodes/{node_id}{path}".format(node_id=self._node_id, path=path), *args, **kwargs)

    def start(self):
        """
        Starts this node instance.
        """

        if self.isStarted():
            log.debug("{} is already running".format(self.name()))
            return

        log.debug("{} is starting".format(self.name()))
        self.post("/start", self._startCallback, timeout=None, showProgress=False)

    def _startCallback(self, result, error=False, **kwargs):
        """
        Callback for start.

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while starting {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
        else:
            self._parseControllerResponse(result)

    def stop(self):
        """
        Stops this node instance.
        """

        if self.status() == Node.stopped:
            log.debug("{} is already stopped".format(self.name()))
            return

        log.debug("{} is stopping".format(self.name()))
        self.post("/stop", self._stopCallback, timeout=None, showProgress=False)

    def _stopCallback(self, result, error=False, **kwargs):
        """
        Callback for stop.

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while stopping {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
            # To avoid blocking the client we consider node as stopped if the node no longer exists
            # or the server doesn't answer
            if "status" not in result or result["status"] == 404:
                self.setStatus(Node.stopped)
        else:
            self._parseControllerResponse(result)

    def suspend(self):
        """
        Suspends this node.
        """

        if self.status() == Node.suspended:
            log.debug("{} is already suspended".format(self.name()))
            return

        log.debug("{} is being suspended".format(self.name()))
        self.post("/suspend", self._suspendCallback, timeout=None, showProgress=False)

    def _suspendCallback(self, result, error=False, **kwargs):
        """
        Callback for suspend.

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while suspending {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
        else:
            self._parseControllerResponse(result)

    def reload(self):
        """
        Reloads this node instance.
        """

        log.debug("{} is being reloaded".format(self.name()))
        self.post("/reload", self._reloadCallback, timeout=None, showProgress=False)

    def _reloadCallback(self, result, error=False, **kwargs):
        """
        Callback for reload.

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while reloading {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
        else:
            self._parseControllerResponse(result)

    def createNodeCallback(self, result):
        """
        Callback when the node has been created on the controller.

        :param result: server response
        """

        result = self._parseControllerResponse(result)
        self._createCallback(result)

        if self._loading:
            self.loaded_signal.emit()
        else:
            self.setInitialized(True)
            self.created_signal.emit(self.id())
            self._module.addNode(self)

    def _createCallback(self, result):
        """
        Create callback to be overloaded for custom handling by a node.
        """
        pass

    def update(self, new_settings, force=False):
        """
        Updates the settings for this node.

        :param new_settings: settings dictionary
        :param force: force this node to update
        """

        params = {}
        for name, value in new_settings.items():
            if name in self._settings:
                if self._settings[name] != value:
                    params[name] = value
            else:
                log.warning("'{}' setting is unknown".format(name))
        if params or force:
            self._updateOnController(params)

    def _prepareBodyForUpdate(self, params):
        """
        Prepares the body for update API call.

        :returns: body for update
        """

        assert self._node_id is not None

        # minimum required settings for update call
        body = {"properties": {},
                "node_type": self.URL_PREFIX,
                "node_id": self._node_id,
                "compute_id": self._compute.id()}

        # There are two kind of properties. The general properties common to all
        # nodes and the specific ones that need to be put in the properties field
        general_node_properties = ("name",
                                   "console",
                                   "console_type",
                                   "x",
                                   "y",
                                   "z",
                                   "locked",
                                   "symbol",
                                   "label",
                                   "port_name_format",
                                   "port_segment_size",
                                   "first_port_name",
                                   "console_auto_start")

        # No need to send this back to the server because these properties are read-only
        ignore_properties = ("console_host",
                             "symbol_url",
                             "width",
                             "height",
                             "node_id")

        for key, value in params.items():
            if key in general_node_properties:
                body[key] = value
            elif key in ignore_properties:
                pass
            else:
                body["properties"][key] = value

        return body

    def _updateOnController(self, params, timeout=60):
        """
        Update the node on the controller.
        """

        log.debug("{} is updating settings: {}".format(self.name(), params))
        body = self._prepareBodyForUpdate(params)
        self.controllerHttpPut("/nodes/{node_id}".format(node_id=self._node_id), self._updateOnControllerCallback, body=body, timeout=timeout, showProgress=False)

    def _updateOnControllerCallback(self, result, error=False, **kwargs):
        """
        Callback for update on the controller (for errors only)

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error:
            self.server_error_signal.emit(self.id(), result["message"])
            return False

    def updateNodeCallback(self, result):
        """
        Callback when the node has been updated on the controller.

        :param result: server response (dict)
        """

        result = self._parseControllerResponse(result)
        self._updateCallback(result)
        self.updated_signal.emit()

    def _updateCallback(self, result):
        """
        Update callback to be overloaded for custom handling by a node.
        """

        pass

    def delete(self, skip_controller=False):
        """
        Deletes this node instance.

        :param skip_controller: True to not delete on the controller (often when already deleted on the server)
        """

        if not skip_controller:
            for link in self.links():
                link.setDeleting()
            self.controllerHttpDelete("/nodes/{node_id}".format(node_id=self._node_id), self._deleteCallback, showProgress=False)
        else:
            self.deleted_signal.emit()
            self._module.removeNode(self)

    def _deleteCallback(self, result, error=False, **kwargs):
        """
        Callback for delete.

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error:
            log.error("error while deleting {}: {}".format(self.name(), result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])

        # delete the node even if there is an error on server side
        self.deleted_signal.emit()
        self._module.removeNode(self)

    def duplicate(self, x, y, z):
        """
        Duplicates this node.
        """

        params = {"x": int(x),
                  "y": int(y),
                  "z": int(z)}

        self.post("/duplicate", self._duplicateCallback, body=params, timeout=None, showProgress=False)

    def _duplicateCallback(self, result, error=False, **kwargs):
        """
        Callback for duplicate (for errors only).

        :param result: server response (dict)
        :param error: indicates an error (boolean)
        """

        if error and "message" in result:
            log.error("Error while duplicating {}: {}".format(self.name(), result["message"]))

    def _parseControllerResponse(self, result):
        """
        Parse node object from controller response.

        :param result: server response (dict)
        """

        if "node_id" in result:
            self._node_id = result["node_id"]

        if "name" in result:
            self.setName(result["name"])

        if "command_line" in result:
            self._command_line = result["command_line"]

        if "node_directory" in result:
            self._node_directory = result["node_directory"]

        if "status" in result:
            if result["status"] == "started":
                self.setStatus(Node.started)
            elif result["status"] == "stopped":
                self.setStatus(Node.stopped)
            elif result["status"] == "suspended":
                self.setStatus(Node.suspended)

        if "ports" in result:
            self._updatePorts(result["ports"])

        if "properties" in result:
            for name, value in result["properties"].items():
                if name in self._settings and self._settings[name] != value:
                    log.debug("{} setting up and updating {} from '{}' to '{}'".format(self.name(), name, self._settings[name], value))
                    self._settings[name] = value

            result.update(result["properties"])
            del result["properties"]

        # Update common element of all nodes
        for key in ["x", "y", "z", "locked", "symbol", "label", "console_host", "console", "console_type", "console_auto_start", "custom_adapters", "first_port_name", "port_name_format", "port_segment_size"]:
            if key in result:
                self._settings[key] = result[key]

        return result

    def _updatePorts(self, ports):
        """
        Update the ports on this node.

        :param ports: array of Port objects
        """

        self._settings["ports"] = ports
        old_ports = self._ports.copy()
        self._ports = []
        for port in ports:
            new_port = None

            # Update port if it already exists
            for old_port in old_ports:
                if old_port.adapterNumber() == port["adapter_number"] and old_port.portNumber() == port["port_number"]:
                    new_port = old_port
                    old_port.setName(port["name"])
                    old_ports.remove(old_port)
                    break

            if new_port is None:
                if port["link_type"] == "serial":
                    new_port = SerialPort(port["name"])
                else:
                    new_port = EthernetPort(port["name"])
            new_port.setShortName(port["short_name"])
            new_port.setAdapterNumber(port["adapter_number"])
            new_port.setPortNumber(port["port_number"])
            new_port.setDataLinkTypes(port["data_link_types"])
            new_port.setStatus(self.status())
            new_port.setAdapterType(port.get("adapter_type"))
            new_port.setMacAddress(port.get("mac_address"))
            self._ports.append(new_port)

    def setGraphics(self, node_item):
        """
        Sync the remote object with the node_item
        """

        data = {"x": int(node_item.pos().x()),
                "y": int(node_item.pos().y()),
                "z": int(node_item.zValue()),
                "symbol": node_item.symbol(),
                "locked": node_item.locked()}

        if node_item.label() is not None:
            data["label"] = node_item.label().dump()

        # Only send the changes
        changed = False
        for key in data:
            if key not in self._settings or self._settings[key] != data[key]:
                changed = True

        if not changed:
            return

        self._updateOnController(data)

    def setPos(self, x, y, z=None):
        """
        Set the position for this node.

        :param x: X coordinate
        :param y: Y coordinate
        :param z: Z coordinate
        """

        self._settings["x"] = int(x)
        self._settings["y"] = int(y)
        if z is not None:
            self._settings["z"] = int(z)

    def consoleCommand(self, console_type=None):
        """
        Returns the console command line for this host

        :returns: console command line (string)
        """

        from .main_window import MainWindow
        general_settings = MainWindow.instance().settings()

        if not console_type:
            console_type = self.consoleType()
        if console_type:
            if console_type == "vnc":
                return general_settings["vnc_console_command"]
            elif console_type.startswith("spice"):
                return general_settings["spice_console_command"]
        return general_settings["telnet_console_command"]

    def consoleType(self):
        """
        Get the console type (serial, telnet or VNC)
        """

        console_type = "none"
        if "console_type" in self.settings():
            return self.settings()["console_type"]
        return console_type

    def consoleHost(self):
        """
        Returns the host to connect to the console.

        :returns: host (string)
        """

        host = self.settings()["console_host"]
        if host is None or host == "::" or host == "0.0.0.0" or host == "0:0:0:0:0:0:0:0":
            host = Controller.instance().host()
        return host

    def setStatus(self, status):
        """
        Overloaded setStatus() method for console auto start.
        """

        if self.status() == status:
            return
        super().setStatus(status)
        if status == self.started and "console_auto_start" in self.settings() and self.settings()["console_auto_start"]:
            # give the node some time to start before opening the console
            QtCore.QTimer.singleShot(1000, self.openConsole)

    def openConsole(self, command=None, aux=False):
        """
        Opens a console.

        :param command: console command line
        :param aux: indicates an auxiliary console
        """

        if command is None:
            if aux:
                command = self.consoleCommand(console_type="telnet")
            else:
                command = self.consoleCommand()

        console_type = "telnet"

        if aux:
            console_port = self.auxConsole()
            if console_port is None:
                raise ValueError("AUX console port not allocated for {}".format(self.name()))
            # AUX console is always telnet
            console_type = "telnet"
        else:
            console_port = self.console()
            if console_port is None:
                log.debug("No console port allocated for {}".format(self.name()))
                return
            if "console_type" in self.settings():
                console_type = self.consoleType()

        if aux is False and self.bringToFront() is True:
            return

        if console_type == "telnet":
            from .telnet_console import nodeTelnetConsole
            nodeTelnetConsole(self, console_port, command)
        elif console_type == "vnc":
            from .vnc_console import vncConsole
            vncConsole(self, console_port, command)
        elif console_type.startswith("spice"):
            from .spice_console import spiceConsole
            spiceConsole(self, console_port, command)
        elif console_type == "http" or console_type == "https":
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("{console_type}://{host}:{port}{path}".format(console_type=console_type, host=self.consoleHost(), port=console_port, path=self.consoleHttpPath())))

    def bringToFront(self):
        """
        Bring the console window to front.
        """

        if self.status() == Node.started:
            if sys.platform.startswith("linux"):
                wmctrl_path = shutil.which("wmctrl")
                if wmctrl_path:
                    try:
                        # use wmctrl to raise the window based on the node name (this doesn't work well with window having multiple tabs)
                        subprocess.run([wmctrl_path, "-Fa", self.name()], check=True, env=os.environ)
                        return True
                    except subprocess.CalledProcessError:
                        log.debug("Could not find window title '{}' to bring it to front".format(self.name()))
                    except OSError as e:
                        log.warning("Count not focus on terminal window: '{}'".format(e))
            elif sys.platform.startswith("win"):
                console_command = self.consoleCommand()
                if console_command:
                    process_name = console_command.split()[0]
                    if bring_window_to_front_from_process_name(process_name, self.name()):
                        return True
                    else:
                        log.debug("Could not find process name '' and window title '{}' to bring it to front".format(process_name, self.name()))

                if bring_window_to_front_from_title(self.name()):
                    return True
                else:
                    log.debug("Could not find window title '{}' to bring it to front".format(self.name()))
        return False

    def importFile(self, path, source_path):
        """
        Imports a file to this node.
        """

        self.post("/files/{path}".format(path=path), self._importFileCallback, body=pathlib.Path(source_path), timeout=None)

    def _importFileCallback(self, result, error=False, **kwargs):
        """
        Callback for import file.
        """

        if error:
            log.error("Error while importing file: {}".format(result["message"]))
            self.server_error_signal.emit(self.id(), result["message"])
            return False

    def exportFile(self, path, output_path):
        """
        Exports a file from this node.
        """

        self.get("/files/{path}".format(path=path), self._exportFileCallback, context={"path": output_path}, raw=True)

    def _exportFileCallback(self, result, error=False, raw_body=None, context={}, **kwargs):
        """
        Callback for export file.
        """

        if not error:
            try:
                with open(context["path"], "wb+") as f:
                    f.write(raw_body)
            except OSError as e:
                log.error("Cannot export file '{}': {}".format(context["path"], e))

    def exportConfigsToDirectory(self, directory):
        """
        Exports the configs to a directory.

        :param directory: destination directory path
        """

        if not self.configFiles():
            return False
        for file in self.configFiles():
            self.get("/files/{file}".format(file=file),
                     self._exportConfigsToDirectoryCallback,
                     context={"directory": directory, "file": file},
                     raw=True)
        return True

    def _exportConfigsToDirectoryCallback(self, result, error=False, raw_body=None, context={}, **kwargs):
        """
        Callback for exportConfigsToDirectory.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error:
            # The file could be missing if there is no private-config for example.
            return

        export_directory = context["directory"]
        # we can have / in the case of Docker
        filename = normalize_filename(self.name()) + "_{}".format(context["file"].replace("/", "_"))
        config_path = os.path.join(export_directory, filename)
        try:
            with open(config_path, "wb") as f:
                log.debug("saving {} config to {}".format(self.name(), config_path))
                f.write(raw_body)
        except OSError as e:
            self.error_signal.emit(self.id(), "could not export config to {}: {}".format(config_path, e))

    def importConfigsFromDirectory(self, directory):
        """
        Imports configs from a directory.

        :param directory: source directory path
        """

        if not self.configFiles():
            return

        try:
            contents = os.listdir(directory)
        except OSError as e:
            self.error_signal.emit(self.id(), "Cannot list file in {}: {}".format(directory, str(e)))
            return

        for file in self.configFiles():
            # we can have / in the case of Docker
            filename = normalize_filename(self.name()) + "_{}".format(file.replace("/", "_"))
            if filename in contents:
                self.post("/files/{file}".format(file=file),
                          self._importConfigsFromDirectoryCallback,
                          pathlib.Path(os.path.join(directory, filename)))
            else:
                log.warning("{}: config file '{}' not found".format(self.name(), filename))

    def _importConfigsFromDirectoryCallback(self, result, error=False, **kwargs):
        """
        Callback for importConfigsFromDirectory.

        :param result: server response
        :param error: indicates an error (boolean)
        """

        if error and "message" in result:
            log.error("Error while import config: {}".format(result["message"]))

    @staticmethod
    def isValidRfc1123Hostname(hostname):
        """
        Validate a hostname according to RFC 1123

        Each element of the hostname must be from 1 to 63 characters long
        and the entire hostname, including the dots, can be at most 253
        characters long.  Valid characters for hostnames are ASCII
        letters from a to z, the digits from 0 to 9, and the hyphen (-).
        A hostname may not start with a hyphen.
        """

        if hostname[-1] == ".":
            hostname = hostname[:-1]  # strip exactly one dot from the right, if present

        if len(hostname) > 253:
            return False

        labels = hostname.split(".")

        # the TLD must be not all-numeric
        if re.match(r"[0-9]+$", labels[-1]):
            return False

        allowed = re.compile(r"(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$")
        return all(allowed.match(label) for label in labels)

    @staticmethod
    def onCloseOptions():
        """
        Returns the on close options.

        :returns: dict
        """

        options = {"Power off the VM": "power_off",
                   "Send the shutdown signal (ACPI)": "shutdown_signal",
                   "Save the VM state": "save_vm_state"}

        return options
