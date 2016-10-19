#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import sys, pickle, signal, threading, time
import spotify

PORT = 8000
MAPPING_FILE = 'floppymapping.pkl'

STATE_IDLE = 0

user_clients = []
last_broadcast = "None"

class DiskHandler(object):

    def __init__(self):
        self.disk_state = STATE_IDLE
        self.current_disk = None

    @staticmethod
    def send_broadcast(message):
        for client in user_clients:
            client.sendMessage(message)
        last_broadcast = message

    @staticmethod
    def resend_last_message(client):
        last_broadcast.sendMessage(last_broadcast)

    def handle_message(self, message):
        self.map_disk(message)

    def disk_signal(self):
        try:
            f = open("/dev/sda", "rb")
            f.seek(0)
            bytes = f.read(32)
            f.close()
            if bytes.encode('hex') != self.current_disk:
                print "DISK " + bytes.encode('hex')
                self.current_disk = bytes.encode('hex')
                self.insert_disk(bytes.encode('hex'))
        except IOError:
            if self.current_disk != None:
                print "NO DISK"
                self.current_disk = None
                self.insert_disk(None)

    def insert_disk(self, disk):
        stop_track()
        if disk is None:
            self.send_broadcast("⏏")
            self.disk_state = STATE_IDLE
            return

        if mapper.exists(disk):
            # self.send_broadcast("DISK: " + disk)
            self.play(mapper.get(disk))
        else:
            self.send_broadcast("💾\nempty")

    def play(self, id):
        track_info = play_track(id)
        self.send_broadcast("▶️ \n" + track_info)

    def map_disk(self, data):
        mapper.set(self.current_disk, data)
        self.send_broadcast("Saved.")
        self.play(data)
        self.disk_state = STATE_IDLE

class DiskWS(WebSocket):

    def handleMessage(self):
        disk_handler.handle_message(self.data)

    def handleConnected(self):
        user_clients.append(self)
        self.sendMessage("Hello.")
        # disk_handler.resend_last_message(self)
        print self.address, 'connected'

    def handleClose(self):
        self.sendMessage("Good bye!")
        print self.address, 'disconnected.'
        try:
            user_clients.remove(self)
        except ValueError:
            pass

class DiskMapper():

    mapping = {}

    def __init__(self):
        self.load()

    def load(self):
        try:
            f = open(MAPPING_FILE, "rb")
            self.mapping = pickle.load(f)
            f.close()
        except (IOError, EOFError):
            pass

    def save(self):
        f = open(MAPPING_FILE, "wb")
        pickle.dump(self.mapping, f)
        f.close()

    def set(self, id, uri):
        self.load()
        self.mapping[id] = uri
        self.save()

    def get(self, id):
        self.load()
        return self.mapping[id]
        self.save()

    def exists(self, id):
        self.load()
        return id in self.mapping

disk_handler = DiskHandler()
mapper = DiskMapper()

def server():
    server = SimpleWebSocketServer('', PORT, DiskWS)
    server.serveforever()

server_thread = threading.Thread(target=server)
server_thread.daemon = True
server_thread.start()

print "Websocket running on port %i." % PORT

from websocket import create_connection

def handle(signal, frame):
    disk_handler.disk_signal()

signal.signal(signal.SIGUSR1, handle)

import sys
sys.tracebacklimit = 100

#Spotfy

# Assuming a spotify_appkey.key in the current dir
session = spotify.Session()

# Process events in the background
loop = spotify.EventLoop(session)
loop.start()

# Connect an audio sink
audio = spotify.AlsaSink(session)

# Events for coordination
logged_in = threading.Event()
end_of_track = threading.Event()


def on_connection_state_updated(session):
    if session.connection.state is spotify.ConnectionState.LOGGED_IN:
        logged_in.set()


def on_end_of_track(self):
    end_of_track.set()

# Register event listeners
session.on(
    spotify.SessionEvent.CONNECTION_STATE_UPDATED, on_connection_state_updated)
session.on(spotify.SessionEvent.END_OF_TRACK, on_end_of_track)

import credentials
session.login(**spotify_login)

def play_track(link_str):
    # Play a track
    try:
        link = session.get_link(link_str)
        track = link.as_track().load()
        session.player.load(track)
        session.player.play()
        return "%s\n%s" % (track.name, ", ".join([a.name for a in track.artists]))
    except ValueError:
        return "disk broken"

def stop_track():
    logged_in.wait()
    session.player.pause()

# Wait for playback to complete or Ctrl+C
try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    exit(0)
