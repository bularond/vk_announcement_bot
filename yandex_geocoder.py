import requests
from settings import yandex_geocoder_key

_ = {
    'GeoObject': {
        'metaDataProperty': {
            'GeocoderMetaData': {
                'kind': 'house',
                'text': 'Россия, Санкт-Петербург, Тверская улица, 6',
                'precision': 'exact',
                'Address': {
                    'country_code': 'RU',
                    'postal_code': '191015',
                    'formatted': 'Россия, Санкт-Петербург, Тверская улица, 6',
                    'Components': [
                        {'kind': 'country', 'name': 'Россия'},
                        {'kind': 'province','name': 'Северо-Западный федеральный округ'},
                        {'kind': 'province', 'name': 'Санкт-Петербург'},
                        {'kind': 'locality', 'name': 'Санкт-Петербург'},
                        {'kind': 'street', 'name': 'Тверская улица'},
                        {'kind': 'house', 'name': '6'}
                    ]
                },
                'AddressDetails': {
                    'Country': {
                        'AddressLine': 'Россия, Санкт-Петербург, Тверская улица, 6',
                        'CountryNameCode': 'RU',
                        'CountryName': 'Россия',
                        'AdministrativeArea': {
                            'AdministrativeAreaName': 'Санкт-Петербург',
                            'Locality': {
                                'LocalityName': 'Санкт-Петербург',
                                'Thoroughfare': {
                                    'ThoroughfareName': 'Тверская улица',
                                    'Premise': {
                                        'PremiseNumber': '6',
                                        'PostalCode': {
                                            'PostalCodeNumber': '191015'
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        'description': 'Санкт-Петербург, Россия',
        'name': 'Тверская улица, 6',
                'boundedBy': {
            'Envelope': {
                'lowerCorner': '30.375723 59.945125',
                'upperCorner': '30.383933 59.949244'
            }
        },
        'Point': {
            'pos': '30.379828 59.947185'
        }
    }
}
_ = {
    'GeoObject': {
        'metaDataProperty': {
            'GeocoderMetaData': {
                'kind': 'street', 
                'text': 'Россия, Санкт-Петербург, Тверская улица', 
                'precision': 'street', 
                'Address': {
                    'country_code': 'RU', 
                    'formatted': 'Россия, Санкт-Петербург, Тверская улица', 
                    'Components': [
                        {'kind': 'country', 'name': 'Россия'}, 
                        {'kind': 'province', 'name': 'Северо-Западный федеральный округ'}, 
                        {'kind': 'province', 'name': 'Санкт-Петербург'}, 
                        {'kind': 'locality', 'name': 'Санкт-Петербург'}, 
                        {'kind': 'street', 'name': 'Тверская улица'}
                    ]
                }, 
                'AddressDetails': {
                    'Country': {
                        'AddressLine': 'Россия, Санкт-Петербург, Тверская улица', 
                        'CountryNameCode': 'RU', 
                        'CountryName': 'Россия', 
                        'AdministrativeArea': {
                            'AdministrativeAreaName': 'Санкт-Петербург', 
                            'Locality': {
                                'LocalityName': 'Санкт-Петербург', 
                                'Thoroughfare': {
                                    'ThoroughfareName': 'Тверская улица'
                                }
                            }
                        }
                    }
                }
            }
        }, 
        'description': 'Санкт-Петербург, Россия', 
        'name': 'Тверская улица', 
        'boundedBy': {
            'Envelope': {
                'lowerCorner': '30.378175 59.94677', 
                'upperCorner': '30.389647 59.946932'
            }
        }, 
        'Point': {'pos': '30.383915 59.946865'}
    }
}

def object_to_need_format(inp):
    '''
    Преобразовывает данные с сайта geocode-maps.yandex.ru 
    '''
    inp = inp['GeoObject']
    out = {
        'city': '',
        'street': '',
        'house': ''
    }
    kind =  inp['metaDataProperty']['GeocoderMetaData']['kind']
    out['full_address'] = inp['metaDataProperty']['GeocoderMetaData']['text']
    out['house_geopos'] = {
        'type': 'Point',
        'coordinates': list(map(float, inp['Point']['pos'].split()))
    }
    components = inp['metaDataProperty']['GeocoderMetaData']['Address']['Components']
    components = {a['kind']: a['name'] for a in components}
    if(kind == 'house' and components.get('street') != None and components.get('locality')):
        out['city'] = components.get('locality')
        out['street'] = components['street']
        out['house'] = components['house']
    elif(kind == 'street' and components.get('locality') != None):
        out['city'] = components.get('locality')
        out['street'] = components['street']
    elif(kind == 'locality'):
        out['city'] = components.get('locality')
    else:
        out = None
    return out

def str_to_geo_data(st):
    """
    : Возвращает dict{'city': str, street':str, 'house':str, 'geocode': geocode, 'full_address': str}
    """
    st = '+'.join(st.split())
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={yandex_geocoder_key}&format=json&geocode={st}"
    respounse = requests.get(url=url)
    data = respounse.json()

    if('error' in data.keys()):
        raise f"Error {data['error']['status']} from geocode-maps.yandex.ru \n Message {data['error']['message']}"
    else:
        data = data['response']['GeoObjectCollection']['featureMember']
        data = map(object_to_need_format, data)
        data = list(filter(lambda a: a != None, data))

        return data

if __name__ == "__main__":
    print(str_to_geo_data("Сочи олимпийский проспект 40"))
