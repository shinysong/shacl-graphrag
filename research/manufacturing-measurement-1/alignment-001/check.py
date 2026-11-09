import diagnostic as d
assert d.quantize(3.5,'nearest_half_up')==4 and d.quantize(3.5,'floor')==3 and d.quantize(3.5,'ceil')==4
r=d.run('/missing');assert len(r['rows'])==144 and all(x['status']=='failed' for x in r['rows']) and r['selected_verified_mapping'] is None
assert len(d.CANDIDATES)==18 and len(set(d.CANDIDATES))==18
print('rounding and144failure denominator,18candidate universe controls passed')
