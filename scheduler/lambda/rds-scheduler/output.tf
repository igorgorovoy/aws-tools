output "rds_scheduler_lambda_function_arn" {
  value = aws_lambda_function.rds_scheduler_lambda.arn
}

output "rds_instance_profile_arn" {
  value = aws_iam_instance_profile.rds_scheduler_instance_profile.arn
}
