#!/usr/bin/env python
# ROS node libs

import rospy
from sensor_msgs.msg import Image,PointCloud2
from std_msgs.msg import Int16, Float32MultiArray
import math
# from cv_bridge import CvBridge, CvBridgeError
import numpy as np
import matplotlib.pyplot as plt
import pickle
from pathlib import Path
from visualization_msgs.msg import Marker,MarkerArray
import torch
from google.protobuf import text_format
# from second.utils import simplevis
from second.pytorch.train import build_network
from second.protos import pipeline_pb2
from second.utils import config_tool
from geometry_msgs.msg import Quaternion, Pose, Point, Vector3
from std_msgs.msg import Header, ColorRGBA
import geometry_msgs.msg as geom_msg
import time
import numpy as np
import time
import os
import natsort
import datetime
from second.pytorch.mayank_play.lidar_point_ops_on_mayavi import draw_lidar_simple

# GPU settings: Select GPUs to use. Coment it to let the system decide
#os.environ["CUDA_VISIBLE_DEVICES"]="0"
def wait_for_time():
    """Wait for simulated time to begin.
    """
    while rospy.Time().now().to_sec() == 0:
        pass

def main():

    def show_text_in_rviz_mullti_cube(boxes_lidar,point_cl_msg,marker_publisher):
        markers_my = MarkerArray()
        markers_my.markers = []
        for i, data in enumerate(boxes_lidar):
            # for i in range(5):
            #     print(time.time())
            ###################################################333333
            # val=data[6]
            # val=math.degrees(val)
            # if val>0:
            #     val=val+0
            # else:
            #     val=360+val
            # val=math.radians(val)
            ################################################################
            marker = Marker(
                type=Marker.CUBE,
                lifetime=rospy.Duration(5),
                pose=Pose(Point(0.5, 0.5, 1.45), Quaternion(0, 0, 0, 1)),
                scale=Vector3(0.6, 0.6, 0.6),
                header=Header(frame_id='base_link'),
                color=ColorRGBA(0.0, 1, 0.0, .4))
            marker.action = Marker.ADD
            marker.ns = "est_pose_" + str(i)
            marker.id = i
            marker.header.stamp = marker.header.stamp
            # marker.pose.orientation.w =1
            marker.pose.position.x = data[0]
            marker.pose.position.y = data[1]
            marker.pose.position.z = data[2]

            marker.pose.orientation.x = 0
            marker.pose.orientation.y = 0
            marker.pose.orientation.z = 0
            marker.pose.orientation.w = data[6]

            marker.scale.x = data[4]
            marker.scale.y = data[3]
            marker.scale.z = data[5]
            # rospy.sleep(1)
            markers_my.markers.append(marker)
            # rospy.sleep(1)
        marker_publisher.publish(markers_my)
        # pcl_publisher.publish(point_cl_msg)



    rospy.init_node('my_node')

    #########################################################################33333
    marker_publisher = rospy.Publisher('mayank_visualization_marker', MarkerArray, queue_size=5)
    pcl_publisher = rospy.Publisher('mayank_pcl', PointCloud2, queue_size=1)
    ##################################################################################

    # ## Initial msg
    rospy.loginfo('  ## Starting ROS  interface ##')
    # ## Load a (frozen) Tensorflow model into memory.
    print("ready to process----------------------------------------------------------")
    ####################################################################################333
    #mayank initialsier
    config_path = "/home/mayank_sati/pycharm_projects/pytorch/second.pytorch_traveller59_date_9_05/second/configs/nuscenes/all.pp.largea.config"
    config = pipeline_pb2.TrainEvalPipelineConfig()
    with open(config_path, "r") as f:
        proto_str = f.read()
        text_format.Merge(proto_str, config)
    input_cfg = config.eval_input_reader
    model_cfg = config.model.second
    # config_tool.change_detection_range(model_cfg, [-50, -50, 50, 50])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # device = torch.device("cpu")
    # ckpt_path = "/home/mayank_sati/pycharm_projects/pytorch/second.pytorch_traveller59_date_9_05/second/mayank_all_fhpd/voxelnet-29325.tckpt"
    ckpt_path = "/home/mayank_sati/pycharm_projects/pytorch/second.pytorch_traveller59_date_9_05/second/point_pp_nuscene/voxelnet-140670.tckpt"
    # ckpt_path = "/home/mayank_sati/pycharm_projects/pytorch/second.pytorch_traveller59_date_9_05/second/eval_result/pretrained_models_v1.5/pp_model_for_nuscenes_pretrain/voxelnet-296960.tckpt"
    net = build_network(model_cfg).to(device).eval()
    net.load_state_dict(torch.load(ckpt_path))
    target_assigner = net.target_assigner
    voxel_generator = net.voxel_generator

    class_names = target_assigner.classes

    grid_size = voxel_generator.grid_size
    feature_map_size = grid_size[:2] // config_tool.get_downsample_factor(model_cfg)
    feature_map_size = [*feature_map_size, 1][::-1]

    anchors = target_assigner.generate_anchors(feature_map_size)["anchors"]
    anchors = torch.tensor(anchors, dtype=torch.float32, device=device)
    anchors = anchors.view(1, -1, 7)
    # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    feature_map_size = [1, 50, 50]
    ret = target_assigner.generate_anchors(feature_map_size)
    class_names = target_assigner.classes
    anchors_dict = target_assigner.generate_anchors_dict(feature_map_size)
    anchors_list = []
    for k, v in anchors_dict.items():
        anchors_list.append(v["anchors"])

    # anchors = ret["anchors"]
    anchors = np.concatenate(anchors_list, axis=0)
    anchors = anchors.reshape([-1, target_assigner.box_ndim])
    assert np.allclose(anchors, ret["anchors"].reshape(-1, target_assigner.box_ndim))
    matched_thresholds = ret["matched_thresholds"]
    unmatched_thresholds = ret["unmatched_thresholds"]
    # anchors_bv = box_np_ops.rbbox2d_to_near_bbox(anchors[:, [0, 1, 3, 4, 6]])
    anchors_bv = 2
    anchor_cache = {
        "anchors": anchors,
        "anchors_bv": anchors_bv,
        "matched_thresholds": matched_thresholds,
        "unmatched_thresholds": unmatched_thresholds,
        "anchors_dict": anchors_dict,
    }
    anchors = torch.tensor(anchors, dtype=torch.float32, device=device)
    anchors = anchors.view(1, -1, 7)




    input_folder = "/home/mayank_sati/Documents/point_clouds/nuscene_v1.0-mini/samples/LIDAR_TOP"
    # input_folder="/home/mayank_sati/Documents/point_clouds/KITTI_DATASET_ROOT/training/velodyne_reduced"
    for root, _, filenames in os.walk(input_folder):
        if (len(filenames) == 0):
            print("Input folder is empty")
            # return 1
        filenames = natsort.natsorted(filenames, reverse=False)

        # time_start = time.time()
        for filename in filenames:
            # try:
            filename = input_folder + '/' + filename
            points = np.fromfile(filename, dtype=np.float32)

            points = points.reshape((-1, 5))[:, :4]
            mypoints = points
    ############################################################################3
            # lidar = np.fromstring(point_cl_msg.data, dtype=np.float32)
            # points = lidar.reshape(-1, 4)
            # if you want to understant this working
            # points = lidar.reshape((-1, 5))[:, :4]
            # fig = draw_lidar_simple(points)
            # points = points.reshape((-1, 4))
            # points = points.reshape((-1, 5))[:, :4]
            # voxels, coords, num_points,voxel_num = voxel_generator.generate(points, max_voxels=20000)
            ####################################################3
            # points = np.fromfile(str(v_path), dtype=np.float32, count=-1).reshape([-1, 5])
            points[:, 3] /= 255
            # draw_lidar_simple(points)

            # points[:, 4] = 0
            #########################################################333
            res = voxel_generator.generate(points, max_voxels=30000)
            voxels = res["voxels"]
            coords = res["coordinates"]
            num_points = res["num_points_per_voxel"]
            num_voxels = np.array([voxels.shape[0]], dtype=np.int64)
            # print("voxel_generator_time",(time.time() - t)*1000)
            ###############################################################
            # print(voxels.shape)
            # add batch idx to coords
            coords = np.pad(coords, ((0, 0), (1, 0)), mode='constant', constant_values=0)
            voxels = torch.tensor(voxels, dtype=torch.float32, device=device)
            coords = torch.tensor(coords, dtype=torch.int32, device=device)
            num_points = torch.tensor(num_points, dtype=torch.int32, device=device)
            # print("conversion time",(time.time() - t)*1000)
            example = {"anchors": anchors, "voxels": voxels, "num_points": num_points, "coordinates": coords, }
            t2 = time.time()
            pred = net(example)[0]
            # print("prediction",(time.time() - t2)*1000)
            # print("total_time",(time.time() - t)*1000)
            boxes_lidar = pred["box3d_lidar"].detach().cpu().numpy()
            scores_lidar = pred["scores"].detach().cpu().numpy()
            labels_lidar = pred["label_preds"].detach().cpu().numpy()
            ##############################3333
            threshold = .4
            keep = np.where((scores_lidar >= threshold))[0]
            scores_lidar = scores_lidar[keep]
            boxes_lidar = boxes_lidar[keep]
            labels_lidar = labels_lidar[keep]
            print(scores_lidar)
            ################################################################################
            # show_text_in_rviz_mullti_cube(boxes_lidar,mypoints,marker_publisher)
            pcl_publisher.publish(mypoints)
            # show_text_in_rviz_mullti_sphere(boxes_lidar,point_cl_msg)

            #here data for publishing





# def main():
#     rospy.init_node('my_node', anonymous=True)
#     tf_ob = ros_tensorflow_obj()
#     tf_ob.run_ponpillars()
#
#     # tf_ob.subscribers_def
#     try:
#         rospy.spin()
#     except KeyboardInterrupt:
#         print("Shutting down")
if __name__ == '__main__':
    main()