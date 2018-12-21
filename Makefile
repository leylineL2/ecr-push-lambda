Bucket ?= MyBucket
Service := Lambda-python
StackName := ConvertECSPythonStack
TARGET := deploy/ECSPushLambda-python.yml
SOURCES := lambda-python.yml lambda-python/convertECR2ECS.py


.PHONY: Lambda-python
$(Service): $(TARGET)
# cloudformation deploy 吐き出されたファイル場所とスタック名を指定
	aws cloudformation deploy --template-file $(TARGET) --stack-name $(StackName) --capabilities CAPABILITY_IAM
$(TARGET): $(SOURCES)
# cloudformation package 一番最初に書いた親Stackファイルと吐き出すファイル場所を指定
	mkdir -p build
	mkdir -p $(dir $(TARGET))
	# pip3 install -r requirements.txt -t lambda/
	#	# pipが動かなかったら
	#	# https://yuzu441.hateblo.jp/entry/2015/10/15/212314
	zip -r build/code-python.zip lambda-python/
	aws cloudformation package --s3-bucket $(Bucket) --template-file $< --output-template-file $(TARGET)
