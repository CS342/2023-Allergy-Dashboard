# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This demo lets you to explore the Udacity self-driving car image dataset.
# More info: https://github.com/streamlit/demo-self-driving

import ast
import json
import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os, urllib, cv2
import firebase_admin
from firebase_admin import credentials, firestore, storage

QUESTIONS_MAP = {
    '661e8930-a2ba-4791-914b-f989327a8cc4': "Please let us know if this account is for you or another individual.",
    'd09b5b5b-f561-4222-9f83-5b7c1ae4731d': "What is your gender?",
    'd101bb2c-a7cf-4086-90f6-fc93bd08dd5e': "What year were you born?",
    '9f860104-9522-41a0-8afa-914f4020a3fe': "Do you identify as:",
    'e9253887-296a-40ee-f672-7abb0d7da17c': "Your zipcode",
    'c92e24da-fb82-4fd3-8d6f-68dc2f31921c': "What option describes your feelings about your skin condition?",
    '7041d8f9-d603-4d5a-8a03-d3933aae9bfd': "How do you describe your skin condition:",
    'fc9131ba-b915-4d78-8b2c-22f9bbcdfdad': "Do you have history of any of these conditions as a child?",
    '91441ae3-d34f-4234-891b-67b514ac4aac': "How often do you experience the symptoms?",
    'cc43010e-ebbc-418f-83c6-151426381496': "Do you have diagnosis of any of these conditions?",
    'b27ae753-cfa7-491d-8a8d-b34e3673eb00': "Where are experincing the symptoms?",
    'b59d7bdb-7432-4a53-9f37-ca08ac4b7242': "Are you willing to tell us about some of your personal habits and interests (It can help us review your exposures to potential allergens and or irritants)?",
    '9c4c1e7b-b7e9-4342-869b-4686615b7f30': "Please share with us the list of ingredients in your products if you suspect any of these products may have worsened your rash.",
    'cfeb233e-67ce-4d8b-8f5b-20fd76bf449e': "If you suspect your eczema may be related to your occupation, please give us a job title and description.",
}
BUCKET = 'cs342-2023-allergy.appspot.com'
FIRESTORE = 'https://cs342-2023-allergy.firebaseio.com/'
ACCOUNTKEY = 'serviceAccountKey.json'

# Streamlit encourages well-structured code, like starting execution in a main() function.
def main():
    # Download external dependencies.
    bucket, client = init_firebase()
    sync_with_firebase(bucket, client)

    df = pd.read_csv('firestore.csv')
    users = list(df.columns[1:])
    usernamers = [df[user][0].replace('_', ' ') for user in users]

    # Once we have the dependencies, add a selector for the app mode on the sidebar.
    st.sidebar.title("Patient Selector")
    name = st.sidebar.selectbox("Please choose a Patient ID to show the questinare and the patch test results.", usernamers)
    user = users[usernamers.index(name)]
    questinare = ast.literal_eval(df[user][1])
    photos = ast.literal_eval(df[user][2])
    metas = ast.literal_eval(df[user][3])
    st.sidebar.success('Patient Selected!')

    st.header('PatchTracker Dashboard')
    st.markdown('This dashboard shows the patch test results for the selected Patient.')
    st.markdown(f'Patient Name: **{name}**')

    st.subheader('Questinare Responses')
    for q in questinare:
        st.metric(label=q, value=questinare[q], delta=None)

    st.text("")
    st.subheader('Captured Photos')
    for split in photos:
        st.markdown(f":frame_with_picture: {split} photo")
        if split in metas:
            st.markdown(f"notes: {metas[split]}")
        image_path = "images/" + photos[split]
        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        st.image(image.astype(np.uint8), use_column_width=True)
        st.text("")

# @st.cache(hash_funcs={firebase_admin.firestore.firestore.DocumentReference: id})
def init_firebase():
    # Init firebase with your credentials
    cred = credentials.Certificate(ACCOUNTKEY)
    try:
        firebase_admin.initialize_app(cred, {'storageBucket': BUCKET, 
                                        'databaseURL': FIRESTORE})
    except ValueError:
        pass
    bucket = storage.bucket()
    client = firestore.client()
    if 'initialized' not in st.session_state:
        st.session_state['initialized'] = True
    return bucket, client

def sync_with_firebase(bucket, client):
    # Load storage bucket
    files = bucket.list_blobs(prefix='users')
    users_list = []
    users_photos = []
    for file in files:
        user_id = file.name.split('/')[1]
        split = file.name.split('/')[2]
        photo_path = file.name.split('/')[3]
        if user_id not in users_list:
            users_list.append(user_id)
            users_photos.append({split: photo_path})
        else:
            users_photos[users_list.index(user_id)][split] = photo_path
    photos_dict = {}
    for i, user in enumerate(users_list):
        photos_dict[user] = users_photos[i]

    # Download images
    photos_meta = {}
    for user in photos_dict:
        for split in photos_dict[user]:
            source_blob_name = 'users/' + user + '/' + split + '/' + photos_dict[user][split]
            destination_file_name = "images/" + user + "-" + photos_dict[user][split]
            os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
            blob = bucket.blob(source_blob_name)
            blob = bucket.get_blob(source_blob_name)
            comment = blob.metadata.get('comment')
            if comment is not None:
                comment = comment.replace('(', ' ').replace(')', ' ')
            photos_meta[user] = {split: comment}
            if not os.path.exists(destination_file_name):
                blob.download_to_filename(destination_file_name)

    # load firestore
    names_dict = {}
    usernames = client.collection(u'users').stream()
    for username in usernames:
        fisrt_name = u'{}'.format(username.to_dict()['firstName'])
        last_name = u'{}'.format(username.to_dict()['lastName'])
        user_id = u'{}'.format(username.to_dict()['id'])
        names_dict[user_id] = f'{fisrt_name.strip()}_{last_name.strip()}'

    firestore_dict = {}
    questionnaire = {}
    for user in photos_dict:
        firestore_dict[user] = {}
        if user in names_dict:
            firestore_dict[user]['name'] = names_dict[user]
        else:
            firestore_dict[user]['name'] = 'Unknown'
        
        collections = client.collection(u'users').document(user).collections()
        for collection in collections:
            for doc in collection.stream():
                doc_dict = doc.to_dict()
                questionnaire = {}
                if doc_dict['resourceType'] == 'QuestionnaireResponse':
                    for item in doc_dict['item']:
                        linkId = item['linkId']
                        if linkId in QUESTIONS_MAP:
                            question_label = QUESTIONS_MAP[linkId]
                            value = item['answer'][0]['valueString']
                            if value.startswith('{'):
                                questionnaire[question_label] = json.loads(value)['code'].replace('-', ' ')
                            elif value.isnumeric():
                                questionnaire[question_label] = ''.join(list(str(value)))
        if questionnaire:
            firestore_dict[user]['questionnaire'] = questionnaire
        else:
            firestore_dict[user]['questionnaire'] = '{}'
        
        firestore_dict[user]['photos'] = {}
        for split in photos_dict[user]:
            firestore_dict[user]['photos'][split] = user + "-" + photos_dict[user][split]

        firestore_dict[user]['meta'] = {}
        for split in photos_meta[user]:
            firestore_dict[user]['meta'][split] = str(photos_meta[user][split])
    pd.DataFrame(firestore_dict).to_csv('firestore.csv')
    return None

if __name__ == "__main__":
    main()
