from stl import mesh
from mpl_toolkits import mplot3d
from matplotlib import pyplot
import os
import logging

def render_stl_to_png(stl_path):

    try:
        # Create a new plot with a square aspect ratio
        figure = pyplot.figure(figsize=(8, 8))  # 8x8 inches square figure
        axes = figure.add_subplot(111, projection='3d')

        # Load the STL files and add the vectors to the plot
        your_mesh = mesh.Mesh.from_file(stl_path)

        # Set labels with units for clarity
        axes.set_xlabel('X (mm)')
        axes.set_ylabel('Y (mm)')
        axes.set_zlabel('Z (mm)')

        # Add the mesh to the plot with a gray color and slight transparency
        mesh_collection = mplot3d.art3d.Poly3DCollection(your_mesh.vectors, facecolor="gray", alpha=.5, linewidths=0.5)
        axes.add_collection3d(mesh_collection)

        # Auto scale to the mesh size
        scale = your_mesh.points.flatten('C')
        axes.auto_scale_xyz(scale, scale, scale)

        # Adjust the view angle for a comprehensive view
        axes.view_init(elev=20, azim=45)

        # Set a neutral background color for the plot for a professional look
        axes.set_facecolor('white')
        figure.patch.set_facecolor('white')

        # Ensure the grid is displayed for better spatial understanding
        axes.grid(True)

        # Define the PNG file path based on the STL file path
        png_path = os.path.splitext(stl_path)[0] + '.png'

        # Save the plot as a square image with high DPI for better quality
        pyplot.savefig(png_path, dpi=300, bbox_inches='tight', pad_inches=0.1, facecolor=figure.get_facecolor())
        # Adjusting the margins to make the model fill the image better
        figure.subplots_adjust(left=0, right=1, bottom=0, top=1)

        # Optionally, show the plot on the screen (remove or comment out if not needed)
        # pyplot.show()

        return png_path
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None
