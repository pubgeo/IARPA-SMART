import boto3
from rasterio.session import AWSSession
import rasterio as rio
from matplotlib.pyplot import imshow
import os
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from stac_query_example import get_bounds_from_geojson, get_bounds_from_kml, searchSTACByBox

def access_images(items, bands=['red', 'green', 'blue']):
    '''
    Accesses images from STAC items and returns them in a dictionary with keys being the item ids and values being dictionaries of band images
    items: a collection of STAC items
    aws_session: an AWS session object
    bands: list of all the bands you want to extract

    return: Dict of all the images. Keys are the id of each item. Values are dictionaries with images for each band.
    '''

    # Convert the collection of items into a dictionary
    items_dict = items.to_dict()['features']

    item_imgs = {}

    # Extract images for each item
    for item in tqdm(items_dict):

        # Get the collection and id
        collection = item['collection']
        
        # Only the l2a collection will work with an AWS account
        if collection != 'sentinel-2-l2a':
            continue

        id = item['id'] 
        item_imgs[id] = {}

        # Get the image for each band
        for band in bands:

            # S3 href is under different name depending on the source
            cog = item['assets'][band]['href']

            # Pull the image from the s3 bucket
            with rio.open(cog) as src:
                #profile = src.profile
                arr = src.read(1)

            # Store the image
            item_imgs[id][band] = arr

    return item_imgs


def plot_images(item_imgs):
    # Combine the images into RGB and view as subplots in a single figure
    num_imgs = len(item_imgs)
    cols = int(np.ceil(np.sqrt(num_imgs)))
    rows = int(np.ceil(num_imgs / cols))

    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 5 * rows))
    axes = np.atleast_1d(axes).flatten()  #ensure a flat array of axes
    for ax, (_, imgs) in zip(axes, item_imgs.items()):
        rgb = np.stack([imgs['red'], imgs['green'], imgs['blue']], axis=2) 
        rgb_scaled = rgb / rgb.max()  # Normalize to [0,1] range for display
        ax.imshow(rgb_scaled)
        ax.axis('off')

    # Hide any unused subplots
    for ax in axes[num_imgs:]:
        ax.set_visible(False)

    plt.tight_layout()
    plt.show()



if __name__ == '__main__':

    bounds_path = '../annotations/primary_dataset/empty_region_models/AE_R001.geojson'

    # Set up spatial bound filtering
    if os.path.splitext(bounds_path)[-1] == '.kml':
        bounds = get_bounds_from_kml(bounds_path)
    elif os.path.splitext(bounds_path)[-1] == '.geojson':
        bounds = get_bounds_from_geojson(bounds_path)
    else:
        print('Please provide a path to a kml or geojson with bounds for spatial filtering. Exiting.')
        exit(1)

    # Set up other filters
    start_date = '2018-01-01'
    end_date = '2018-01-10'
    cloud_cover_ceiling = 20


    # Query for Landsat-8 imagery data
    sensor = 'S2'
    s2_items = searchSTACByBox(sensor=sensor, bbox=bounds, dates=f'{start_date}/{end_date}',
                    cloudCover=cloud_cover_ceiling, verbose=True, collection='Sensor-Specific')


    # Extract the images
    s2_imgs = access_images(s2_items, bands=['red','green','blue'])

    # Plot the images
    plot_images(s2_imgs)


    


