output "asg_scheduler_lambda_function_arn" {
  value = aws_lambda_function.asg_scheduler_lambda.arn
}

output "asg_instance_profile_arn" {
  value = aws_iam_instance_profile.asg_scheduler_instance_profile.arn
}
