import os
import subprocess
import tempfile
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessStart
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch.substitutions import EnvironmentVariable, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare(package='robot_description').find('robot_description')
    # Gazebo resolves `model://<name>/...` by searching resource paths for a folder named `<name>`.
    # If `ros_gz_sim create` translates package URIs into `model://robot_description/...`,
    # the resource root must be the parent directory of the package share folder.
    pkg_share_parent = os.path.dirname(pkg_share)
    default_model_path = os.path.join(pkg_share, 'models', 'robot.xacro')
    default_rviz_config_path = os.path.join(pkg_share, 'rviz', 'urdf_config.rviz')
    default_world_path = os.path.join(pkg_share, 'worlds', 'empty.sdf')
    gz_bridge_params_path = os.path.join(pkg_share, 'config', 'gz_bridge.yaml')

    gui = LaunchConfiguration('gui')
    model = LaunchConfiguration('model')
    rviz_config_file = LaunchConfiguration('rviz_config_file')
    use_gz = LaunchConfiguration('use_gz')
    gz_gui = LaunchConfiguration('gz_gui')
    world = LaunchConfiguration('world')
    gz_home = LaunchConfiguration('gz_home')
    use_robot_state_pub = LaunchConfiguration('use_robot_state_pub')
    use_rviz = LaunchConfiguration('use_rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')

    declare_model_path_cmd = DeclareLaunchArgument(
        name='model',
        default_value=default_model_path,
        description='Absolute path to robot xacro file',
    )

    declare_rviz_config_file_cmd = DeclareLaunchArgument(
        name='rviz_config_file',
        default_value=default_rviz_config_path,
        description='Full path to the RVIZ config file to use',
    )
    declare_use_joint_state_publisher_cmd = DeclareLaunchArgument(
        name='gui',
        default_value='true',
        description='Flag to enable joint_state_publisher_gui',
    )
    declare_use_robot_state_pub_cmd = DeclareLaunchArgument(
        name='use_robot_state_pub',
        default_value='true',
        description='Whether to start the robot state publisher',
    )
    declare_use_rviz_cmd = DeclareLaunchArgument(
        name='use_rviz',
        default_value='true',
        description='Whether to start RVIZ',
    )

    declare_use_gz_cmd = DeclareLaunchArgument(
        name='use_gz',
        default_value='false',
        description='Whether to start Gazebo (gz-sim) and spawn the robot',
    )

    declare_gz_gui_cmd = DeclareLaunchArgument(
        name='gz_gui',
        default_value='true',
        description='If true, start Gazebo with GUI; otherwise server/headless',
    )

    declare_world_cmd = DeclareLaunchArgument(
        name='world',
        default_value=default_world_path,
        description='World (SDF) file to load in Gazebo (gz-sim)',
    )

    declare_gz_home_cmd = DeclareLaunchArgument(
        name='gz_home',
        default_value=PathJoinSubstitution([EnvironmentVariable('PWD'), '.gz']),
        description='GZ_HOME directory (where gz-sim writes logs/config). Set to a writable path.',
    )

    declare_use_sim_time_cmd = DeclareLaunchArgument(
        name='use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true',
    )

    robot_description = Command(['xacro ', model])

    def launch_setup(context, *args, **kwargs):
        model_str = context.perform_substitution(model)
        fd, urdf_path = tempfile.mkstemp(prefix='robot_description_', suffix='.urdf')
        os.close(fd)
        subprocess.run(['xacro', '-o', urdf_path, model_str], check=True)

        gz_sim_gui = ExecuteProcess(
            condition=IfCondition(
                PythonExpression(
                    ["'", use_gz, "' == 'true' and '", gz_gui, "' == 'true'"]
                )
            ),
            cmd=['gz', 'sim', '-r', world],
            output='screen',
        )

        gz_sim_headless = ExecuteProcess(
            condition=IfCondition(
                PythonExpression(
                    ["'", use_gz, "' == 'true' and '", gz_gui, "' != 'true'"]
                )
            ),
            cmd=['gz', 'sim', '-r', '-s', world],
            output='screen',
        )

        # Spawn robot into Gazebo from the URDF we generated above.
        # Trigger on Gazebo process start (event-driven, avoids fragile sleeps).
        spawn_robot = ExecuteProcess(
            condition=IfCondition(use_gz),
            cmd=[
                'ros2',
                'run',
                'ros_gz_sim',
                'create',
                '-name',
                'robot',
                '-file',
                urdf_path,
            ],
            output='screen',
        )

        spawn_on_gz_start = RegisterEventHandler(
            condition=IfCondition(use_gz),
            event_handler=OnProcessStart(
                target_action=gz_sim_gui,
                on_start=[spawn_robot],
            ),
        )

        spawn_on_gz_headless_start = RegisterEventHandler(
            condition=IfCondition(use_gz),
            event_handler=OnProcessStart(
                target_action=gz_sim_headless,
                on_start=[spawn_robot],
            ),
        )

        return [
            Node(
                condition=UnlessCondition(gui),
                package='joint_state_publisher',
                executable='joint_state_publisher',
                name='joint_state_publisher',
                output='screen',
                arguments=[urdf_path],
                parameters=[{'use_sim_time': use_sim_time}],
            ),
            Node(
                condition=IfCondition(gui),
                package='joint_state_publisher_gui',
                executable='joint_state_publisher_gui',
                name='joint_state_publisher_gui',
                output='screen',
                arguments=[urdf_path],
                parameters=[{'use_sim_time': use_sim_time}],
            ),
            Node(
                condition=IfCondition(use_robot_state_pub),
                package='robot_state_publisher',
                executable='robot_state_publisher',
                parameters=[
                    {
                        'use_sim_time': use_sim_time,
                        'robot_description': robot_description,
                        # Ensure TF is available even before joint_states arrive (prevents RViz RobotModel "No transform" errors)
                        'publish_default_positions': True,
                    }
                ],
            ),
            Node(
                condition=IfCondition(use_rviz),
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_config_file],
                parameters=[{'use_sim_time': use_sim_time}], 
            ),
            gz_sim_gui,
            gz_sim_headless,
            spawn_on_gz_start,
            spawn_on_gz_headless_start,
        ]

    ld = LaunchDescription()
    ld.add_action(declare_model_path_cmd)
    ld.add_action(declare_rviz_config_file_cmd)
    ld.add_action(declare_use_joint_state_publisher_cmd)
    ld.add_action(declare_use_robot_state_pub_cmd)
    ld.add_action(declare_use_rviz_cmd)
    ld.add_action(declare_use_gz_cmd)
    ld.add_action(declare_gz_gui_cmd)
    ld.add_action(declare_world_cmd)
    ld.add_action(declare_gz_home_cmd)
    ld.add_action(SetEnvironmentVariable(name='GZ_HOME', value=gz_home))
    # Make sure Gazebo can resolve `model://robot_description/...` URIs.
    ld.add_action(
        SetEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=os.pathsep.join(
                [pkg_share_parent, os.environ.get('GZ_SIM_RESOURCE_PATH', '')]
            ).strip(os.pathsep),
        )
    )
    # Back-compat for older env var name used by Ignition/Gazebo.
    ld.add_action(
        SetEnvironmentVariable(
            name='IGN_GAZEBO_RESOURCE_PATH',
            value=os.pathsep.join(
                [pkg_share_parent, os.environ.get('IGN_GAZEBO_RESOURCE_PATH', '')]
            ).strip(os.pathsep),
        )
    )
    gz_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '--ros-args', '-p',
            f'config_file:={gz_bridge_params_path}'
        ],
        output='screen'
    )
    ld.add_action(gz_bridge_node)
    ld.add_action(declare_use_sim_time_cmd)
    ld.add_action(OpaqueFunction(function=launch_setup))
    return ld
