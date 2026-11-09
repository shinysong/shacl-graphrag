import tempfile
from pathlib import Path
import projection as p
prefix='<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"><NamespaceUris>{}</NamespaceUris><Models/><Aliases>{}</Aliases>{}</UANodeSet>'
def parse(tmp,uris,aliases,nodes):
 f=tmp/'x.xml';f.write_text(prefix.format(''.join('<Uri>'+u+'</Uri>' for u in uris),aliases,nodes));return p.parse(f)
with tempfile.TemporaryDirectory() as d:
 tmp=Path(d)
 a=parse(tmp,['urn:a','urn:b'],'<Alias Alias="T">ns=2;i=4</Alias>','<UAVariable NodeId="ns=1;i=2" BrowseName="1:X" DataType="T"><References><Reference ReferenceType="i=47" IsForward="false">ns=2;i=4</Reference></References></UAVariable>')
 b=parse(tmp,['urn:b','urn:a'],'<Alias Alias="T">ns=1;i=4</Alias>','<UAVariable NodeId="ns=2;i=2" BrowseName="2:X" DataType="T"><References><Reference ReferenceType="i=47" IsForward="0">ns=1;i=4</Reference></References></UAVariable>')
 assert not p.compare(a,b)['changed_definitions'];assert a['aliases']==b['aliases']
 for aliases,nodes in [('<Alias Alias="X">X</Alias>',''),('','<UAObject NodeId="ns=4;i=1" BrowseName="X"/>'),('','<UAObject NodeId="i=1" BrowseName="X"/><UAObject NodeId="i=1" BrowseName="Y"/>'),('','<UAObject NodeId="s=unsupported" BrowseName="X"/>')]:
  try:parse(tmp,['urn:a'],aliases,nodes)
  except ValueError:pass
  else:raise AssertionError('invalid accepted')
print('namespace permutation/direction equivalence plus four invalid input checks pass')
