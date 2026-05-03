# LIDAR robot setup

This repo containes a ROS2 package that represents a mobile robot with LIDAR. It can be used for LIDAR projects. RViz and Gazebo are synced.

![](meta/gazebo.png)
![](meta/rviz.png)

## Demo
![](meta/demo.gif)

## Build

```bash
mkdir -p ~/ros_ws/src
cd ~/ros_ws/src
git clone https://github.com/FrenkenFlores/ros2-mobile-robot.git robot_description
cd ~/ros_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## Launch

RViz + Robot state publisher + Joint state publisher:
```bash
ros2 launch robot_description launch.py
```
RViz + Robot state publisher + Joint state publisher + Gazebo:
```bash
ros2 launch robot_description launch.py use_gz:=true use_sim_time:=true
```
To control the robot use teleop_twist_keyboard
```bash
# Install keyboard control
sudo apt install ros-jazzy-teleop-twist-keyboard
# In separate terminal
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

## LIDAR/SLAM
Launch the slam_toolbox and from RViz set the new fixed frame as `map`

![](meta/slam.png)

```bash
# Install SLAM toolbox
sudo apt install ros-jazzy-slam-toolbox
# In separate terminal. Launch the SLAM.
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=true slam_params_file:=robot_description/config/slam_params.yaml
# In separate termial. Build the map
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```