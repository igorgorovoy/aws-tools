data "archive_file" "lambda" {
  type        = "zip"
  source_file = "lambda_function.py"
  output_path = "lambda_function.zip"
}


resource "aws_lambda_layer_version" "layer" {
  provider            = aws.Blue
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
resource "aws_lambda_function" "rds_scheduler_lambda" {
  provider      = aws.Blue
  function_name = "rds_scheduler"
  handler       = "lambda_function.lambda_handler"
  role          = data.terraform_remote_state.iam.outputs.iam_role_rds_scheduler_lambda
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
      REGION        = "eu-west-1"
      SSM_PARAMETER = "/rds/disable-instances"
      INSTANCES = jsonencode([
        "athena-dev-banking-migrated",
        "athena-dev-dwh-migrated",
        "athena-dev-management-accounting-migrated",
        "athena-dev-trading-processor-migrated",
        "athena-devrds-migrated"
      ])
      EXCLUDED_INSTANCES = jsonencode([
        "multiregion-dev-vault"

      ])
    }
  }

  tags = {
    Name        = "rds_scheduler"
    Environment = "dev"
    Terraform   = "true"
  }
}


# Instance Profile for rds
resource "aws_iam_instance_profile" "rds_scheduler_instance_profile" {
  provider = aws.Blue
  name     = "RDSSchedulerLambdaProfile"
  role     = "RDSSchedulerLambda"
}


# CloudWatch Event Rule для ACTION=enable
resource "aws_cloudwatch_event_rule" "lambda_schedule_enable" {
  provider            = aws.Blue
  name                = "rds_scheduler-enable-schedule"
  description         = "Trigger Lambda function to enable instances daily at 5:30 UTC"
  schedule_expression = "cron(30 5 * * ? *)"
  state               = "ENABLED"
}


# CloudWatch Event Target для ACTION=enable
resource "aws_cloudwatch_event_target" "trigger_lambda_enable" {
  provider  = aws.Blue
  rule      = aws_cloudwatch_event_rule.lambda_schedule_enable.name
  target_id = "rds_scheduler-enable"
  arn       = aws_lambda_function.rds_scheduler_lambda.arn

  input = jsonencode({
    ACTION = "enable"
  })
}


# Permission for CloudWatch to Invoke the Lambda Function
resource "aws_lambda_permission" "allow_cloudwatch_enable" {
  provider      = aws.Blue
  statement_id  = "AllowExecutionFromCloudWatchEnabled"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_scheduler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule_enable.arn
}


# CloudWatch Event Rule для ACTION=disable
resource "aws_cloudwatch_event_rule" "lambda_schedule_disable" {
  provider            = aws.Blue
  name                = "rds_scheduler-disable-schedule"
  description         = "Trigger Lambda function to disable instances daily at 19:00 UTC"
  schedule_expression = "cron(0 19 * * ? *)"
  state               = "ENABLED"
}


# CloudWatch Event Target для ACTION=disable
resource "aws_cloudwatch_event_target" "trigger_lambda_disable" {
  provider  = aws.Blue
  rule      = aws_cloudwatch_event_rule.lambda_schedule_disable.name
  target_id = "rds_scheduler-disable"
  arn       = aws_lambda_function.rds_scheduler_lambda.arn

  input = jsonencode({
    ACTION = "disable"
  })
}


# Permission for CloudWatch to Invoke the Lambda Function
resource "aws_lambda_permission" "allow_cloudwatch_disable" {
  provider      = aws.Blue
  statement_id  = "AllowExecutionFromCloudWatchDisabled"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_scheduler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule_disable.arn
}