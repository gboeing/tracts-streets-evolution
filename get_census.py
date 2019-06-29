# Module: getcensus
# Author: Geoff Boeing
# Description: Download tract-level census variables from the API
# https://www.census.gov/data/developers/guidance/api-user-guide.Query_Components.html
# 
import numpy as np
import pandas as pd
import requests
import time




def download_state_tracts_vars(api_key, dataset, variables, state, year, clean, print_mode):
    """
    download a set of census variables for all tracts in a state
    """
    
    url_template = 'https://api.census.gov/data/{year}/{dataset}?key={api_key}&get={variables}&for=tract:*&in=state:{state}'
    url = url_template.format(year=year, dataset=dataset, api_key=api_key, variables=variables, state=state)
    
    if print_mode is not None:
        if print_mode == 'url':
            print(url)
        elif print_mode == 'state':
            print(state, end=' ')
        else:
            print('.', end='')
    
    try:
        response = requests.get(url, timeout=30)
        json_data = response.json()

        # load as dataframe and index by geoid (state+county+tract)
        df = pd.DataFrame(json_data)
        df = df.rename(columns=df.iloc[0]).drop(df.index[0])
        df['geoid'] = df.apply(lambda row: '{}{}{}'.format(row['state'], row['county'], row['tract']), axis='columns')
        df = df.set_index('geoid').drop(['state', 'county', 'tract'], axis='columns')
        
        if clean:
            df = clean_census_data(df)
        
        return df

    except Exception as e:
        print(e, response.status_code, response.text, response.url, 'PAUSING THEN RE-TRYING')
        time.sleep(10)
        return download_state_tracts_vars(api_key, dataset, variables, state, year, clean, print_mode)
    
    



def download_census(api_key, dataset, year, variables, states, clean, print_mode):
    
    var_str = ','.join(variables)
    df = pd.DataFrame()
    
    for state in states:
        # get census vars for all tracts in this state and append them to df
        df_tmp = download_state_tracts_vars(api_key=api_key, dataset=dataset, year=year,
                                            variables=var_str, state=state, clean=clean,
                                            print_mode=print_mode)
        df = df.append(df_tmp)

    return df.sort_index()
    
    




def clean_census_data(df):
    """
    Clean up the census data results from the API. By default, the census data often
    includes non-numeric characters as annotations or missing values.

    # see https://www.census.gov/data/developers/data-sets/acs-5year/data-notes.html
    # for estimate and annotation values
    
    # A '+' following a median estimate means the median falls in the upper interval 
    # of an open-ended distribution.
    
    # A '-' entry in the estimate column indicates that either no sample observations 
    # or too few sample observations were available to compute an estimate, or a ratio 
    # of medians cannot be calculated because one or both of the median estimates falls 
    # in the lowest interval or upper interval of an open-ended distribution.
    
    # An 'N' entry in the estimate and margin of error columns indicates that data for 
    # this geographic area cannot be displayed because the number of sample cases is too 
    # small.
    
    # An '(X)' means that the estimate is not applicable or not available.
    """
    
    # clean up any non-numeric strings, column by column
    df = df.astype(str)
    bad_strings = ['-', 'N', '(X)', '*']
    for col in df.columns:
        
        # replace any cell with '-' or 'N' or '(X)' or '*' in this column with NaN
        df[col] = df[col].map(lambda value: np.nan if any(s in value for s in bad_strings) else value)
        
        # if every result in this col was replaced by nans, then col is now of type
        # float and we can skip the following cleaning step
        if not df[col].dtype==np.float64:
            # strip out any '+' or ',' or '*'
            df[col] = df[col].str.replace('+', '').str.replace(',', '')
    
    # convert data to floats, assert uniqueness, and return
    def convert_float(value):
        try:
            return float(value)
        except:
            print('error', value, '\n', df)
            return np.nan
    df = df.applymap(convert_float)
    
    assert df.index.is_unique
    
    return df




def chunks(l, n):
    """
    yield successive n-sized chunks from list l
    """
    for i in range(0, len(l), n):
        yield l[i:i+n]
