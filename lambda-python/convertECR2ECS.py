import json
import boto3
import sys
import os
import zipfile
import traceback
from botocore.client import Config

print('Loading function')

code_pipeline = boto3.client('codepipeline')
elbclient = boto3.client('elbv2')


def put_job_success(job, message):
    """Notify CodePipeline of a successful job
    Args:
        job: The CodePipeline job ID
        message: A message to be logged relating to the job status
    Raises:
        Exception: Any exception thrown by .put_job_success_result()
    """
    print('Putting job success')
    print(message)
    code_pipeline.put_job_success_result(jobId=job)


def put_job_failure(job, message):
    """Notify CodePipeline of a failed job
    Args:
        job: The CodePipeline job ID
        message: A message to be logged relating to the job status
    Raises:
        Exception: Any exception thrown by .put_job_failure_result()
    """
    print('Putting job failure')
    print(message)
    code_pipeline.put_job_failure_result(jobId=job, failureDetails={'message': message, 'type': 'JobFailed'})


def continue_job_later(job, message):
    """Notify CodePipeline of a continuing job
    This will cause CodePipeline to invoke the function again with the
    supplied continuation token.
    Args:
        job: The JobID
        message: A message to be logged relating to the job status
        continuation_token: The continuation token
    Raises:
        Exception: Any exception thrown by .put_job_success_result()
    """

    # Use the continuation token to keep track of any job execution state
    # This data will be available when a new job is scheduled to continue the current execution
    continuation_token = json.dumps({'previous_job_id': job})

    print('Putting job continuation')
    print(message)
    code_pipeline.put_job_success_result(jobId=job, continuationToken=continuation_token)


def get_artifact(job_id,job_data):
    print('get Artifact')
    try:
        input_artifact = job_data['inputArtifacts'][0]
        input_s3_location = input_artifact['location']['s3Location'] 
        bucket = input_s3_location['bucketName']
        key = input_s3_location['objectKey']
        print("bucket:"+bucket)
        print("key:"+key)
    except Exception as e:
        put_job_failure(job_id,e)
        raise Exception('Input Artifacts convert to reteral')
        
    try:
        print('Get S3 Object')
        s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
        s3_client.download_file(bucket, key, '/tmp/downloaded_object')
        print('Unzipping')
        zip_ref = zipfile.ZipFile('/tmp/downloaded_object', 'r')
        zip_ref.extractall('/tmp/downloaded_folder')
        zip_ref.close()
        with open('/tmp/downloaded_folder/imageDetail.json','r') as data_file:
            input_json = data_file.read()
        return input_json
    except Exception as e:
        put_job_failure(job_id,e)
        raise Exception('Input Artifacts did not get S3')


def create_image_definition(job_id,input_json):
    print('Shaping JSON')
    try:
        input_dict = json.loads(input_json)
        output_dict = []
        name = input_dict['RepositoryName'].split('/')[-1]
        imageUri = input_dict['ImageURI']
        output_dict.append({"name":name,"imageUri":imageUri})
        output_json = json.dumps(output_dict)
        print(output_json)
        return output_json
    except Exception as e:
        put_job_failure(job_id,e)
        raise Exception('Outputs Artifacts convert to reteral')
    

def put_artifact(job_id,job_data,image_definition_json):
    print('put Artifact')
    try:
        output_artifact = job_data['outputArtifacts'][0]
        output_s3_location = output_artifact['location']['s3Location'] 
        bucket = output_s3_location['bucketName']
        key = output_s3_location['objectKey']
    except Exception as e:
        put_job_failure(job_id,e)
        raise Exception('Outputs Artifacts convert to reteral')

    try:
        print('Zipping')
        # zipping
        os.makedirs('/tmp/.test',exist_ok=True)
        with open('/tmp/.test/imagedefinitions.json','w+') as idf:
            idf.write(image_definition_json)
        import shutil
        shutil.make_archive('/tmp/upload_object','zip',root_dir='/tmp/.test')
        # put object
        print('Put S3 Object')
        s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
        s3_client.upload_file('/tmp/upload_object.zip',bucket, key)
    except Exception as e:
        put_job_failure(job_id,e)
        raise Exception('Output Artifacts dose not put S3 or missed zip')


def handler(event, context):
    """ Main haldler as an entry point of the AWS Lambda function. Handler controls the sequence of methods to call
    1. Read Job Data from input json
    2. Read Job ID from input json
    3. Get parameters from input json
    4. Get Artifact for  ECR from S3 
    5. Shaping ECR Artifact to ECS format
    6. Put Artifact for ECS to S3
    7. Send success or failure to codepipeline
                Args:
                    event : http://docs.aws.amazon.com/codepipeline/latest/userguide/actions-invoke-lambda-function.html
                    #actions-invoke-lambda-function-json-event-example
                    context: not used but required for Lambda function
                Raises:
                    Exception: Any exception thrown by handler
    """

    try:
        job_id = event['CodePipeline.job']['id']
        job_data = event['CodePipeline.job']['data']
        input_json = get_artifact(job_id,job_data)
        output_json = create_image_definition(job_id,input_json)
        put_artifact(job_id,job_data,output_json)
        put_job_success(job_id,"Shaping Artifact Success!")

    except Exception as e:
        print('Function failed due to exception.')
        print(e)
        traceback.print_exc()
        put_job_failure(job_id, 'Function exception: ' + str(e))

    print('Function complete.')
    return "Complete!"

if __name__ == "__main__":
    handler(sys.argv[0], None)
