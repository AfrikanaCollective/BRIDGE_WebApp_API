from mongoengine import DynamicDocument, StringField, DateTimeField, connect

# MongoDB connect

def get_mongo_connection():

    return connect(
        db='bridge_development',
        host='mongodb://localhost:27017',
        username='bridge',
        password='@Dmin2o13!',
        authentication_source='admin',  # likely needed if you created user in admin DB
    )

class PaperRecordCollection(DynamicDocument):
    meta = {'collection': 'neonatal_records'}  # custom collection name
    id = StringField(primary_key=True)
    hospital = StringField(required=True)
    record_type = StringField(required=True)
    admission_date_manual = DateTimeField(required=True)
    discharge_date_manual = DateTimeField(required=True)
