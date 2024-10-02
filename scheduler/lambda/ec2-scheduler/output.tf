output "ec2_scheduler_lambda_function_arn" {
  value = aws_lambda_function.ec2_scheduler_lambda.arn
}

output "ec2_instance_profile_arn" {
  value = aws_iam_instance_profile.ec2_scheduler_instance_profile.arn
}
