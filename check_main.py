import re

p = 'C:/Users/JerryJoel/OneDrive - Cloud Destinations Infotech Pvt Ltd/Documents/Projects/License Management Tool - Updated UI/Frontend/backend/main.py'
s = open(p, encoding='utf-8').read()
print('has api/v1:', 'api/v1' in s)
print('has LicenseRequest:', 'LicenseRequest' in s)
print('has /requests:', '/requests' in s)
print('prefixes:', re.findall(r'prefix="[^"]+"', s))
print('routes:')
for m in re.findall(r'@app\.(get|post|put|patch)\("([^"]+)"', s):
    print('  ', m)
