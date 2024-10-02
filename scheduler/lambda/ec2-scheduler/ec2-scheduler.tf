data "archive_file" "lambda" {
  type        = "zip"
  source_file = "lambda_function.py"
  output_path = "lambda_function.zip"
}


resource "aws_lambda_layer_version" "layer" {
  provider            = aws.Green
  layer_name          = "python-custom-layer"
  description         = "python-custom-layer"
  compatible_runtimes = ["python3.12"]

  filename                 = "lambda_function.zip"
  source_code_hash         = filebase64sha256("lambda_function.zip")
  compatible_architectures = ["x86_64", "arm64"]
}


output "layer_arn" {
  value = aws_lambda_layer_version.layer.arn
}


# Lambda Function
resource "aws_lambda_function" "ec2_scheduler_lambda" {
  provider      = aws.Green
  function_name = "ec2_scheduler"
  handler       = "lambda_function.lambda_handler"
  role          = data.terraform_remote_state.iam.outputs.iam_role_ec2_scheduler_lambda
  runtime       = "python3.12"
  filename      = "lambda_function.zip"

  source_code_hash = data.archive_file.lambda.output_base64sha256

  timeout = 60 # Set timeout to 1 minute (60 seconds)

  layers = [
    #"arn:aws:lambda:eu-central-1:294949574448:layer:python-custom-layer:3"
     aws_lambda_layer_version.layer.arn
  ]

  environment {
    variables = {
      ACTION        = "enable"
      REGION        = "eu-central-1"
      SSM_PARAMETER = "/ec2/developers-disable-instances"
      INSTANCES = jsonencode([
        "i-0f655bd83bd781b09",
        "i-0b51e80a3aed8b2f3",
        "i-0cd77cfb615c32cb7",
        "i-0c3244c33dccd2e5b",
        "i-0810ab9036e010310",
        "i-051b2779f4549849d",
        "i-059a229c4c8dc8e94"
      ])
      EXCLUDED_INSTANCES = jsonencode([
        "i-09722b6eda50d6423",
        "i-036c0dfea02cf95e2",
        "i-027f922e837fb4304",
        "i-0413186a7c5a98249",
        "i-033b661ddab1fd1bd"
      ])
    }
  }

  tags = {
    Name        = "ec2_scheduler"
    Environment = "dev"
    Terraform   = "true"
  }
}


# Instance Profile for EC2
resource "aws_iam_instance_profile" "ec2_scheduler_instance_profile" {
  provider = aws.Green
  name     = "Ec2SchedulerLambdaProfile"
  role     = "Ec2SchedulerLambda" #data.terraform_remote_state.iam.outputs.iam_role_ec2_scheduler_lambda
}


## CloudWatch Event Rule for Scheduling the Lambda Function
#resource "aws_cloudwatch_event_rule" "lambda_schedule" {
#  provider            = aws.Green
#  name                = "ec2_scheduler-on"
#  description         = "Trigger Lambda function daily at 6:00 UTC"
#  schedule_expression = "cron(0 6 * * ? *)" # Run at 06:00 UTC every day
#  state               = "ENABLED"           # Temporarily disable the scheduler
#}
#
## CloudWatch Event Target to Link Rule to Lambda Function
#resource "aws_cloudwatch_event_target" "trigger_lambda" {
#  provider  = aws.Green
#  rule      = aws_cloudwatch_event_rule.lambda_schedule.name
#  target_id = "ec2_scheduler-lambda"
#  arn       = aws_lambda_function.ec2_scheduler_lambda.arn
#}
#
## Permission for CloudWatch to Invoke the Lambda Function
#resource "aws_lambda_permission" "allow_cloudwatch" {
#  provider      = aws.Green
#  statement_id  = "AllowExecutionFromCloudWatch"
#  action        = "lambda:InvokeFunction"
#  function_name = aws_lambda_function.ec2_scheduler_lambda.function_name
#  principal     = "events.amazonaws.com"
#  source_arn    = aws_cloudwatch_event_rule.lambda_schedule.arn
#}

# CloudWatch Event Rule для ACTION=enable
resource "aws_cloudwatch_event_rule" "lambda_schedule_enable" {
  provider            = aws.Green
  name                = "ec2_scheduler-enable-schedule"
  description         = "Trigger Lambda function to enable instances daily at 5:30 UTC"
  schedule_expression = "cron(30 5 * * ? *)"
  state               = "ENABLED"
}


# CloudWatch Event Target для ACTION=enable
resource "aws_cloudwatch_event_target" "trigger_lambda_enable" {
  provider  = aws.Green
  rule      = aws_cloudwatch_event_rule.lambda_schedule_enable.name
  target_id = "ec2_scheduler-enable"
  arn       = aws_lambda_function.ec2_scheduler_lambda.arn

  input = jsonencode({
    ACTION = "enable"
  })
}


# Permission for CloudWatch to Invoke the Lambda Function
resource "aws_lambda_permission" "allow_cloudwatch_enable" {
  provider      = aws.Green
  statement_id  = "AllowExecutionFromCloudWatchEnabled"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ec2_scheduler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule_enable.arn
}





# CloudWatch Event Rule для ACTION=disable
resource "aws_cloudwatch_event_rule" "lambda_schedule_disable" {
  provider            = aws.Green
  name                = "ec2_scheduler-disable-schedule"
  description         = "Trigger Lambda function to disable instances daily at 19:00 UTC"
  schedule_expression = "cron(0 23 * * ? *)"
  state               = "ENABLED"
}


# CloudWatch Event Target для ACTION=disable
resource "aws_cloudwatch_event_target" "trigger_lambda_disable" {
  provider  = aws.Green
  rule      = aws_cloudwatch_event_rule.lambda_schedule_disable.name
  target_id = "ec2_scheduler-disable"
  arn       = aws_lambda_function.ec2_scheduler_lambda.arn

  input = jsonencode({
    ACTION = "disable"
  })
}


# Permission for CloudWatch to Invoke the Lambda Function
resource "aws_lambda_permission" "allow_cloudwatch_disable" {
  provider      = aws.Green
  statement_id  = "AllowExecutionFromCloudWatchDisabled"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ec2_scheduler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule_disable.arn
}