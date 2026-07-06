"""
Subscribe to `smart-campus/events/alert` and print received messages.
Usage:
  pip install paho-mqtt
  python subscribe_alerts.py --host localhost --port 1883
  python subscribe_alerts.py --host broker.example.com --port 1883 --topic "smart-campus/events/#"
"""
import argparse
import json
import sys

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker")
        client.subscribe(userdata['topic'])
        print(f"Subscribed to {userdata['topic']}")
    else:
        print(f"Connect failed with code {rc}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        try:
            obj = json.loads(payload)
            pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            print(f"\n[{msg.topic}]\n{pretty}\n")
        except Exception:
            print(f"\n[{msg.topic}] {payload}\n")
    except Exception as e:
        print(f"Error decoding message: {e}")


def main():
    parser = argparse.ArgumentParser(description='Subscribe and print alerts')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--topic', default='smart-campus/events/alert')
    parser.add_argument('--username', help='MQTT username (optional)')
    parser.add_argument('--password', help='MQTT password (optional)')
    args = parser.parse_args()

    userdata = {'topic': args.topic}
    client = mqtt.Client(userdata=userdata)
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(args.host, args.port, 60)
    except Exception as e:
        print(f"Cannot connect to broker {args.host}:{args.port} -> {e}")
        sys.exit(1)

    client.loop_forever()


if __name__ == '__main__':
    main()
