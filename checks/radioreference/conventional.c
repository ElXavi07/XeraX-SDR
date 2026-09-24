// SPDX-License-Identifier: GPL-3.0-or-later
#include "rr_soap.h"
#include <dsd-neo/runtime/radioreference.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fails;
static void test(rr_shape shape,const char* fragment,int expected,const char* name,long long hz){
 char xml[4096];snprintf(xml,sizeof(xml),"<Envelope><Body><response><return>%s</return></response></Body></Envelope>",fragment);
 dsd_rr_conventional_list list={0};dsd_rr_error error={0};
 int rc=rr_soap_parse(xml,strlen(xml),shape,&list,&error,NULL);
 if(rc || list.count!=1 || list.items[0].id!=expected || strcmp(list.items[0].name,name)||list.items[0].frequency_hz!=hz){fprintf(stderr,"shape %d failed: rc=%d count=%zu detail=%s\n",shape,rc,list.count,error.detail);fails++;}
 if(shape==RR_SHAPE_CONV_FREQUENCIES&&list.count==1){
  if(strcmp(list.items[0].tone,"100.0 PL")||strcmp(list.items[0].tags,"Fire Dispatch")||strcmp(list.items[0].color_code,"3")||strcmp(list.items[0].mode,"2")){fprintf(stderr,"frequency metadata mismatch\n");fails++;}
 }
 free(list.items);
}
int main(){
 test(RR_SHAPE_CONV_CATEGORIES,"<cats><item><cName>Public safety</cName><subcats><item><scid>44</scid><scName>Fire</scName><lat>33.7</lat><lon>-116.2</lon></item></subcats></item></cats>",44,"Fire",0);
 test(RR_SHAPE_CONV_AGENCIES,"<agencyList><item><aid>5</aid><aName>County agency</aName></item></agencyList>",5,"County agency",0);
 test(RR_SHAPE_CONV_MODES,"<item><mode>2</mode><modeName>FMN</modeName></item>",2,"FMN",0);
 test(RR_SHAPE_CONV_FREQUENCIES,"<item><fid>22</fid><out>155.250000</out><alpha>Dispatch</alpha><descr>County dispatch</descr><mode>2</mode><enc>0</enc><tone>100.0 PL</tone><colorCode>3</colorCode><tags><item><tagDescr>Fire Dispatch</tagDescr></item></tags></item>",22,"Dispatch",155250000);
 return fails?1:0;
}
