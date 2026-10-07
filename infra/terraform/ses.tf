# Alert e-mails (SPEC 4.10). A domain identity needs its DKIM records in DNS; an address identity
# only needs the confirmation link in the mail AWS sends.
resource "aws_sesv2_email_identity" "sender" {
  email_identity = var.ses_sender
}
