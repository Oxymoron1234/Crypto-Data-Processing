import json
import base64

def dynamodb_json_to_dict(dynamodb_json):
    """
    Convert DynamoDB JSON format to standard JSON format with correct data types.
    """
    output = {}
    for key, value in dynamodb_json.items():
        if "S" in value:
            output[key] = value["S"]
        elif "N" in value:
            output[key] = float(value["N"])
        elif "BOOL" in value:
            output[key] = value["BOOL"]
        elif "NULL" in value:
            output[key] = None
        elif "L" in value:
            output[key] = [dynamodb_json_to_dict(i) if isinstance(i, dict) else i for i in value["L"]]
        elif "M" in value:
            output[key] = dynamodb_json_to_dict(value["M"])
        else:
            output[key] = value
    return output

def lambda_handler(event, context):
    transformed_records = []

    for record in event["records"]:
        # Decode base64 encoded Kinesis data
        payload = base64.b64decode(record['data']).decode("utf-8")
        raw_data = json.loads(payload)
        
        # Extract NewImage (latest item state)
        if "dynamodb" in raw_data and "NewImage" in raw_data["dynamodb"]:
            transformed_data = dynamodb_json_to_dict(raw_data["dynamodb"]["NewImage"])
            transformed_data["event_name"] = raw_data.get("eventName", "UNKNOWN")
            transformed_data["event_id"] = raw_data.get("eventID", "UNKNOWN")

            transformed_data_str = json.dumps(transformed_data) + '\n'
            transformed_data_encoded = base64.b64encode(transformed_data_str.encode('utf-8')).decode('utf-8')
            
            transformed_records.append({
                'recordId': record['recordId'],
                'result': 'Ok',
                'data': transformed_data_encoded
            })

    return {
        "records" : transformed_records
    }