#!/usr/bin/python
#
# Copyright (c) 2016 The Ontario Institute for Cancer Research. All rights reserved.
#
# This program and the accompanying materials are made available under the terms of the GNU Public License v3.0.
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
# SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import logging
import click
from icgcget.clients.ega.ega_client import EgaDownloadClient
from icgcget.clients.errors import SubprocessError
from icgcget.clients.gdc.gdc_client import GdcDownloadClient
from icgcget.clients.icgc.storage_client import StorageClient
from icgcget.clients.pdc.pdc_client import PdcDownloadClient
from icgcget.clients.gnos.gnos_client import GnosDownloadClient

from utils import check_access, api_error_catch, get_entities, match_repositories


class AccessCheckDispatcher(object):
    def __init__(self):
        self.logger = logging.getLogger("__log__")

    def access_checks(self, repo_list, file_ids, manifest, cghub_access, cghub_path, ega_access, gdc_access,
                      icgc_access, pdc_access, pdc_path, pdc_region, output, api_url):
        cghub_ids = []
        gdc_ids = []
        pdc_urls = []
        gdc_client = GdcDownloadClient()
        ega_client = EgaDownloadClient()
        gt_client = GnosDownloadClient()
        icgc_client = StorageClient()
        pdc_client = PdcDownloadClient()

        entities = get_entities(self, manifest, file_ids, api_url, repo_list)
        for entity in entities:
            repository, copy = match_repositories(self, repo_list, entity)
            if repository == "gdc":
                gdc_ids.append(entity["dataBundle"]["dataBundleId"])
            if repository == "cghub":
                cghub_ids.append(entity["dataBundle"]["dataBundleId"])
            if repository == "pdc":
                pdc_urls.append('s3' + copy['repoBaseUrl'][5:] + copy["repoDataPath"])

        if "collaboratory" in repo_list:
            check_access(self, icgc_access, "icgc")
            self.access_response(icgc_client.access_check(icgc_access, repo="collab", api_url=api_url),
                                 "Collaboratory.")
        if "aws-virginia" in repo_list:
            check_access(self, icgc_access, "icgc")
            self.access_response(icgc_client.access_check(icgc_access, repo="aws", api_url=api_url),
                                 "Amazon Web Server.")
        if 'ega' in repo_list:
            check_access(self, ega_access, 'ega')
            self.access_response(ega_client.access_check(ega_access), "EGA.")

        if 'gdc' in repo_list and gdc_ids:
            check_access(self, gdc_access, 'gdc')
            gdc_result = api_error_catch(self, gdc_client.access_check, gdc_access, gdc_ids)
            self.access_response(gdc_result, "GDC files specified.")

        if 'cghub' in repo_list and cghub_ids:  # as before, can't check cghub permissions without files
            check_access(self, cghub_access, 'cghub', cghub_path)

        try:
            self.access_response(gt_client.access_check(cghub_access, cghub_ids, cghub_path, output=output),
                                 "CGHub files.")
        except SubprocessError as ex:
            self.logger.error(ex.message)
            raise click.Abort

        if 'pdc' in repo_list and pdc_urls:
            check_access(self, pdc_access, 'pdc', pdc_path)
            try:
                self.access_response(pdc_client.access_check(pdc_access, pdc_urls, pdc_path, output=output,
                                                             region=pdc_region), "PDC files.")
            except SubprocessError as ex:
                self.logger.error(ex.message)
                raise click.Abort

    def access_response(self, result, repo):
        if result:
            self.logger.info("Valid access to the " + repo)
        else:
            self.logger.info("Invalid access to the " + repo)