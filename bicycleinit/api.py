import datetime
import json
import logging
import os
import base64
import mimetypes

import requests


def time(api_url, timeout=5):
  try:
    url = f'{api_url}/api/v2/time'
    payload = {"client_time": datetime.datetime.now(datetime.UTC).isoformat()}
    response = requests.post(url, json=payload, timeout=timeout)
    if response.status_code == 200:
      content = response.json()
      logging.info(f"Client time {payload['client_time']}")
      logging.info(f"Server time {content['server_time']}")
      logging.info(f"Time delta  {content['diff']}")
    else:
      logging.info(f"wifi.time: {response.status_code} for {url}")
    return response.status_code == 200
  except requests.RequestException:
    return False

def register(api_url, timeout=5):
  # Get hostname, username, and MAC address
  hostname = os.uname().nodename
  username = os.getlogin()

  # Load configuration from bicycleinit.json
  config_path = 'bicycleinit.json' if os.path.exists('bicycleinit.json') else 'bicycleinit-default.json'
  with open(config_path, 'r') as f:
    payload = json.load(f)

  # Add hostname and username to payload
  payload["hostname"] = hostname
  payload["username"] = username

  try:
    response = requests.post(
        f"{api_url}/api/v2/register",
        json=payload,
        timeout=timeout,
        headers={"Content-Type": "application/json"}
    )

    if response.status_code != 201:
      logging.info(f"/api/v2/register: Registration response: {response.status_code} {response.text}")
      return False

    config = response.json()
    # save config to file
    with open('bicycleinit.json', 'w') as f:
      json.dump(config, f, indent=2)
      logging.info("/api/v2/register: Saved new configuration to bicycleinit.json")

    return True
  except requests.RequestException as e:
    logging.error(f"/api/v2/register: Registration failed: {e}")
    return False


def config(api_url, ident, timeout=5):
  try:
    response = requests.post(
        f"{api_url}/api/v2/config",
        json={'ident': ident},
        timeout=timeout,
        headers={"Content-Type": "application/json"}
    )

    if response.status_code != 200:
      logging.info(f"Config response: {response.status_code} {response.text}")
      return False

    config = response.json()
    # save config to file
    with open('bicycleinit.json', 'w') as f:
      json.dump(config, f, indent=2)
      logging.info("/api/v2/config: Saved new configuration to bicycleinit.json")

    return True
  except requests.RequestException as e:
    logging.error(f"Config failed: {e}")
    return False

def upload_pending(ident, server, current_session, skipCurrentLogFile=False):
  if not os.path.exists('sessions'):
    return

  pending_dir = os.path.join('sessions')
  sessions = [name for name in os.listdir(pending_dir) if os.path.isdir(os.path.join(pending_dir, name))]
  sessions.sort(reverse=True)

  for session in sessions:
    session_path = os.path.join(pending_dir, session)
    files = [name for name in os.listdir(session_path) if os.path.isfile(os.path.join(session_path, name))]
    files.sort()
    try:
      for file in files:
        if skipCurrentLogFile and session == current_session and file == 'bicycleinit.log':
          continue  # Skip current log file

        filepath = os.path.join(session_path, file)
        # Detect if the file is a PNG image and read appropriately
        _, ext = os.path.splitext(file)
        ext = ext.lower()
        data = None
        encoding = None
        mimetype = None

        if ext in  ['.png', '.jpg', '.jpeg', '.dng']:
          # Read binary and base64-encode for JSON transport
          with open(filepath, 'rb') as f:
            raw = f.read()
          data = base64.b64encode(raw).decode('ascii')
          encoding = 'base64'
          mimetype = mimetypes.types_map.get(ext, 'application/octet-stream')
        else:
          # Default: read as text
          with open(filepath, 'r') as f:
            data = f.read()

        try:
          datetime.datetime.strptime(file[:16], '%Y%m%d-%H%M%S-')
          upload_name = file[16:]
        except ValueError:
          upload_name = file

        payload = {
          'ident': ident,
          'session': session,
          'path': '',
          'filename': upload_name,
          'data': data
        }

        # If binary data was used, include encoding and mimetype metadata
        if encoding is not None:
          payload['encoding'] = encoding
        if mimetype is not None:
          payload['mimetype'] = mimetype
        response = requests.post(f'{server}/api/v2/session/upload', json=payload, timeout=10)
        if response.status_code == 200:
          os.remove(filepath)
          logging.info(f"Uploaded and deleted file: {filepath}")
          if session == current_session and file == 'bicycleinit.log':
            # Create new empty log file
            with open(filepath, 'w') as new_log:
              new_log.write('')
        else:
          logging.warning(f"Failed to upload file {filepath}: {response.status_code}, {response.text}")
          return
    except Exception as e:
      logging.error(f"An error occurred: {e}")

    # After all files are uploaded, remove the session directory if it's not the current session
    if session != current_session:
      try:
        os.rmdir(session_path)
      except OSError as e:
        logging.error(f"Failed to delete directory {session_path}: {e}")
      else:
        logging.info(f"Deleted session directory: {session}")
    else:
      logging.info(f"Skipping deletion of current session directory: {session}")
