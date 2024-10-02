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
resource "aws_lambda_function" "eks_scheduler_lambda" {
  provider      = aws.Blue
  function_name = "eks_scheduler"
  handler       = "lambda_function.lambda_handler"
  role          = data.terraform_remote_state.iam.outputs.iam_role_eks_scheduler_lambda
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
      CLUSTER_NAME  = "dev-1-30"
      SSM_PARAMETER = "/eks/disable-instances"
      EXCLUDED_NODEGROUPS = jsonencode([
        "dev-ondemand-gp3-20240724153425537700000062t",
        "dev-ondemand_styd-gp3-20240930102001513800000009"
#        "dev-spots-x64-2024093010200151470000000b",
#        "dev-common-spots-gp3-20240930104106310100000001"
      ])
    }
  }

  tags = {
    Name        = "eks_scheduler"
    Environment = "dev"
    Terraform   = "true"
  }
}


# Instance Profile for eks
resource "aws_iam_instance_profile" "eks_scheduler_instance_profile" {
  provider = aws.Blue
  name     = "eksSchedulerLambdaProfile"
  role     = "eksSchedulerLambda"
}


# CloudWatch Event Rule для ACTION=enable
resource "aws_cloudwatch_event_rule" "lambda_schedule_enable" {
  provider            = aws.Blue
  name                = "eks_scheduler-enable-schedule"
  description         = "Trigger Lambda function to enable instances daily at 5:30 UTC"
  schedule_expression = "cron(30 5 * * ? *)"
  state               = "ENABLED"
}


# CloudWatch Event Target для ACTION=enable
resource "aws_cloudwatch_event_target" "trigger_lambda_enable" {
  provider  = aws.Blue
  rule      = aws_cloudwatch_event_rule.lambda_schedule_enable.name
  target_id = "eks_scheduler-enable"
  arn       = aws_lambda_function.eks_scheduler_lambda.arn

  input = jsonencode({
    ACTION = "enable"
  })
}


# Permission for CloudWatch to Invoke the Lambda Function
resource "aws_lambda_permission" "allow_cloudwatch_enable" {
  provider      = aws.Blue
  statement_id  = "AllowExecutionFromCloudWatchEnabled"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eks_scheduler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule_enable.arn
}


# CloudWatch Event Rule для ACTION=disable
resource "aws_cloudwatch_event_rule" "lambda_schedule_disable" {
  provider            = aws.Blue
  name                = "eks_scheduler-disable-schedule"
  description         = "Trigger Lambda function to disable instances daily at 19:00 UTC"
  schedule_expression = "cron(0 23 * * ? *)"
  state               = "ENABLED"
}


# CloudWatch Event Target для ACTION=disable
resource "aws_cloudwatch_event_target" "trigger_lambda_disable" {
  provider  = aws.Blue
  rule      = aws_cloudwatch_event_rule.lambda_schedule_disable.name
  target_id = "eks_scheduler-disable"
  arn       = aws_lambda_function.eks_scheduler_lambda.arn

  input = jsonencode({
    ACTION = "disable"
  })
}


# Permission for CloudWatch to Invoke the Lambda Function
resource "aws_lambda_permission" "allow_cloudwatch_disable" {
  provider      = aws.Blue
  statement_id  = "AllowExecutionFromCloudWatchDisabled"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eks_scheduler_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule_disable.arn
}