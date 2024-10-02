output "eks_scheduler_lambda_function_arn" {
  value = aws_lambda_function.eks_scheduler_lambda.arn
}

output "eks_instance_profile_arn" {
  value = aws_iam_instance_profile.eks_scheduler_instance_profile.arn
}
