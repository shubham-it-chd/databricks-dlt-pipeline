# Terraform: Secure Cross-Account Connectivity – Databricks ↔ RDS PostgreSQL (Different AWS Accounts)

This guide provides production-ready Terraform code to securely connect a **Databricks workspace** (Account A) to an **RDS PostgreSQL instance** (Account B) **without exposing anything to the public internet**.

**Recommended & Official Solution**: **AWS PrivateLink (Interface VPC Endpoints)**  
**Alternative**: VPC Peering (included for completeness)

---

## Architecture Overview
