output "api_gateway_url" {
  description = "API Gateway endpoint URL for the contact form API"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/contact"
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.contact_form.function_name
}

output "sender_email" {
  description = "Email address used to send contact form messages"
  value       = local.email_config.sender_email
}

output "recipient_email" {
  description = "Email address that receives contact form messages"
  value       = local.email_config.recipient_email
}