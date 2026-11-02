import sys
import rclpy
from rclpy.node import Node
from turtlesim.srv import Kill

def main():
    names=sys.argv[1:]
    if not names: raise SystemExit('ERROR no turtles requested')
    rclpy.init()
    node=Node('fleet_capture_cleanup')
    try:
        client=node.create_client(Kill,'/kill')
        if not client.wait_for_service(timeout_sec=10): raise RuntimeError('/kill unavailable')
        for name in names:
            request=Kill.Request(); request.name=name
            future=client.call_async(request)
            rclpy.spin_until_future_complete(node,future,timeout_sec=10)
            if not future.done() or future.exception() is not None or future.result() is None:
                raise RuntimeError('failed /kill '+name)
            print('KILLED',name,flush=True)
        print('KILL PASS',flush=True)
    finally:
        node.destroy_node();rclpy.shutdown()
if __name__=='__main__': main()
