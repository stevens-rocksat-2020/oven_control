import oven.oven_pb2 as oven_proto

points = [(0, 30),
(60, 150),
(150, 150),
(210, 220), 
(273, 30),
(274, 0)]


def reflow_profile_configuration():
    config = oven_proto.OvenConfiguration()

    for point in points:
        p = oven_proto.ReflowPoint()
        p.time = int(point[0] * 1000)
        p.temp = point[1]
        config.reflowCurve.reflowPoints.extend([p])
    return config

    
