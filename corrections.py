from datetime import datetime
import logging
import os

import pandas as pd
import pdmongo as pdm
import pymongo

CLIENT = pymongo.MongoClient(host='xenon1t-daq.lngs.infn.it',
                               username='corrections',
                               password=os.environ['CORRECTIONS_PASSWORD'])
DATABASE_NAME = 'arctic'
DATABASE = CLIENT[DATABASE_NAME]


def initialize():
    """Deletes everything then reinitializes"""
    for collection in DATABASE.list_collections():
        DATABASE.drop_collection(collection['name'])

def list_corrections():
    """Smart logic to list corrections
    """
    return [x['name'] for x in DATABASE.list_collections() if x['name'] != 'global']

def read(correction):
    """Smart logic to read corrections
    """ 
    df = pdm.read_mongo(correction, [], DATABASE)

    # No data found
    if df.size == 0:
        return None
    # Delete internal Mongo identifier
    del df['_id']

    # Set UTC
    #df['index'] = pd.to_datetime(df['index'], utc=True)
    
    return df.set_index('index')

def interpolate(what, when, how='interpolate'):
    df = what
    
    df_new = pd.DataFrame.from_dict({'Time' : [when],
                                    # 'This' : [True]
                                    })
    df_new = df_new.set_index('Time')
    
    df_combined = pd.concat([df,
                             df_new],
                            sort=False)
    df_combined = df_combined.sort_index()
    if how == 'interpolate':
        df_combined = df_combined.interpolate(method='linear')
    elif how == 'fill':
        df_combined = df_combined.ffill()
    else:
        raise ValueError()
        
    return df_combined
    return z[z['This'] == True]

def get_context_config(when, global_version = 'g1'):
    """Global configuration logic
    
    g1 is 'version 1' but can tell difference in versions.
    """ 
    df_global = read('global')
    
    context_config = {}
    
    for correction, version in df_global.iloc[-1][global_version].items():
        df = read(correction)

        df = interpolate(df, when)
        context_config[correction] = df.loc[df.index == when, version].values[0]
    
    return context_config

def write(correction, df):
    """Smart logic to write corrections
    """
    if 'ONLINE' not in df.columns:
        raise ValueError('Must specify ONLINE column')
    if 'v1' not in df.columns:
        raise ValueError('Must specify v1 column')
       
    # Set UTC
    #df.index = df.index.tz_localize('UTC')
    
    # Compare against
    logging.info('Reading old values for comparison')
    df2 = read(correction)
    
    if df2 is not None:
        logging.info('Checking if columns unchanged in past')

        now = datetime.now()
        for column in df2.columns:
            logging.debug('Checking %s' % column)
            if not (df2.loc[df2.index < now, column] == df.loc[df.index < now, column]).all():
                raise ValueError("%s changed in past, not allowed" % column)

    df = df.reset_index()

    logging.info('Writing')
    return df.to_mongo(correction, DATABASE, if_exists='replace')
