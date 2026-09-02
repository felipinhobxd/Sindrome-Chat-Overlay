# Azure Artifact Signing setup

The Windows release workflow is intentionally fail-closed. It will not publish an unsigned
portable executable or installer. Azure Artifact Signing must be configured before this branch
is merged into `main` or the release workflow is started manually.

Artifact Signing is a paid Azure service and its public-trust certificate profile requires
Microsoft identity validation. The validated legal identity determines the publisher shown by
Windows. Do not create a self-signed replacement and do not commit a PFX file, private key, Azure
credential, or client secret to this repository.

## 1. Create the Azure signing resources

1. Use an Azure subscription supported by Artifact Signing.
2. Create an Artifact Signing account in an available region.
3. Complete the required identity validation.
4. Create a public-trust certificate profile for Windows code signing.
5. Record the account endpoint, signing account name, and certificate profile name.

Microsoft setup documentation:

- [Artifact Signing overview and setup](https://learn.microsoft.com/azure/artifact-signing/)
- [Set up signing integrations](https://learn.microsoft.com/azure/artifact-signing/how-to-signing-integrations)

## 2. Configure passwordless GitHub OIDC access

Create a Microsoft Entra application/service principal and add a federated identity credential
with these values:

| Field | Value |
| --- | --- |
| Issuer | `https://token.actions.githubusercontent.com` |
| Subject | `repo:felipinhobxd/Sindrome-Chat-Overlay:environment:production-signing` |
| Audience | `api://AzureADTokenExchange` |

Assign the service principal the **Artifact Signing Certificate Profile Signer** role at the
narrowest scope that contains the selected certificate profile. A client secret is not needed.

Microsoft OIDC documentation:

- [Use Azure Login with OpenID Connect](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [Artifact Signing GitHub Action](https://github.com/Azure/artifact-signing-action)

## 3. Configure the GitHub environment

Create a GitHub Actions environment named `production-signing`. Requiring a reviewer for this
environment is recommended so an unexpected workflow cannot silently use the signing identity.

Add these environment secrets:

| Secret | Purpose |
| --- | --- |
| `AZURE_CLIENT_ID` | Entra application/client ID used by OIDC |
| `AZURE_TENANT_ID` | Microsoft Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription containing Artifact Signing |

Add these environment variables:

| Variable | Purpose |
| --- | --- |
| `AZURE_ARTIFACT_SIGNING_ENDPOINT` | Regional account endpoint, including `https://` |
| `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME` | Artifact Signing account name |
| `AZURE_ARTIFACT_SIGNING_CERTIFICATE_PROFILE` | Public-trust certificate profile name |

The preflight step reports only missing setting names; it never prints their values. GitHub gets a
short-lived Azure token via OIDC for each workflow run.

## 4. Release guarantees

For every release, `.github/workflows/build-windows.yml`:

1. tests and builds the portable executable;
2. signs and RFC 3161 timestamps the portable executable;
3. builds the installer containing that signed executable;
4. signs and timestamps the installer;
5. checks that both Authenticode signatures are `Valid` and have the same publisher subject;
6. calculates SHA-256 only after signing;
7. publishes the files only if every previous step passed.

The app updater independently downloads `SHA256SUMS.txt` and the exact versioned installer asset,
checks size and SHA-256, asks Windows to validate Authenticode, and compares the new publisher with
the publisher of the currently running signed executable. It asks the user again before starting
the installer.

Code signing substantially improves publisher identification, but SmartScreen reputation is also
built over time. A newly issued certificate or rarely downloaded version may still show a warning.
