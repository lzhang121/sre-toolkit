// Loaded only from the same protected SCM revision as the Jenkinsfile.
// Parse JSON in the existing Python runtime; no Pipeline Utility Steps needed.
def configFields(String kind, String path) {
    def output
    withEnv(["SRE_CONFIG_KIND=${kind}", "SRE_CONFIG_FILE=${path}", "SRE_ENV=${params.ENVIRONMENT}"]) {
        output = sh(returnStdout: true, encoding: 'UTF-8', script: '''#!/usr/bin/env bash
set -euo pipefail
python3 -m sretoolkit.jenkins_config "$SRE_CONFIG_KIND" "$SRE_CONFIG_FILE" "$SRE_ENV"
''')
    }
    def values = [:]
    for (line in output.trim().split('\n')) {
        def pair = line.split('\t', 2)
        if (pair.length != 2) { error('Invalid configuration response') }
        values[pair[0]] = pair[1]
    }
    return values
}

def prepare(String phase) {
    def settings = configFields('environment', 'configs/inventory.json')
    withEnv(["SRE_ENV=${params.ENVIRONMENT}", "SRE_TARGETS=${params.TARGETS}",
             "SRE_TASK=${params.TASK}", "SRE_PARAMS=${params.TASK_PARAMS}", "SRE_PHASE=${phase}"]) {
        sh '''#!/usr/bin/env bash
set -euo pipefail
python3 -m sretoolkit.fleet prepare --inventory configs/inventory.json \
  --environment "$SRE_ENV" --targets "$SRE_TARGETS" --task "$SRE_TASK" \
  --params "$SRE_PARAMS" --phase "$SRE_PHASE" --out reports/run
'''
    }
    return settings
}

def execute(Map settings, boolean apply = false, String digest = '', String approver = '') {
    int code
    withCredentials([
        sshUserPrivateKey(credentialsId: settings.ssh_credential_id, keyFileVariable: 'SRE_KEY'),
        file(credentialsId: settings.known_hosts_credential_id, variable: 'SRE_KNOWN_HOSTS'),
        file(credentialsId: settings.ssh_config_credential_id, variable: 'SRE_SSH_CONFIG')
    ]) {
        withEnv(["SRE_COMMAND=${apply ? 'apply' : 'execute'}", "SRE_DIGEST=${digest}", "SRE_APPROVER=${approver}"]) {
            code = sh(returnStatus: true, script: '''#!/usr/bin/env bash
set -euo pipefail
args=()
if [[ "$SRE_COMMAND" == apply ]]; then
  args+=(--approval-digest "$SRE_DIGEST" --approver "$SRE_APPROVER")
fi
python3 -m sretoolkit.fleet "$SRE_COMMAND" --out reports/run \
  --key "$SRE_KEY" --known-hosts "$SRE_KNOWN_HOSTS" --ssh-config "$SRE_SSH_CONFIG" "${args[@]}"
''')
        }
    }
    if (code == 1) { unstable('One or more health checks reported warnings') }
    else if (code != 0) { error("SRE execution failed (exit ${code}); inspect archived results") }
}

def archive() {
    if (fileExists('reports/run/manifest.json')) {
        // Nonzero check status must not mask an original abort or failure.
        sh returnStatus: true, script: 'python3 -m sretoolkit.fleet finalize --out reports/run'
        archiveArtifacts artifacts: 'reports/run/*.json,reports/run/*.csv,reports/run/*.html,reports/run/events/*.json',
                         excludes: 'reports/run/inventory.json,reports/run/extra.json',
                         allowEmptyArchive: false, fingerprint: true
    }
}

return this
