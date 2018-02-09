#!/bin/bash

currentdir=$(pwd)
scriptpath=$(dirname "$0")
cd $scriptpath
scriptpath=$(pwd)
cd $currentdir

source $scriptpath/.setenv.sh

dump_data=0
clear_data=0
import_data=0
sync_media=0
if [[ "$1" == "data" ]] && [[ "$2" == "dump" ]]
then
    dump_data=1
elif [[ "$1" == "data" ]] && [[ "$2" == "import" ]]; then
    import_data=1
elif [[ "$1" == "data" ]] && [[ "$2" == "clear" ]]; then
    clear_data=1
elif [[ "$1" == "data" ]] && [[ "$2" == "" ]]; then
    dump_data=1
    import_data=1
elif [[ "$1" == "media" ]]; then
    sync_media=1
elif [[ "$1" == "" ]]; then
    dump_data=1
    import_data=1
    sync_media=1
fi

if [[ ! -d /tmp/cswmigration ]]
then
    mkdir /tmp/cswmigration
fi

if [[ "$cswhome" == "" ]]
then
    cswhome=$(dirname "$scriptpath")
fi

if [[ $dump_data -eq 1 ]] || [[ $import_data -eq 1 ]]
then
#dump database data.
    tables=(catalogue_organization catalogue_organization_id_seq catalogue_collaborator catalogue_collaborator_id_seq catalogue_pycswconfig catalogue_pycswconfig_id_seq catalogue_tag catalogue_tag_id_seq catalogue_record catalogue_record_id_seq catalogue_record_tags catalogue_record_tags_id_seq catalogue_style catalogue_style_id_seq catalogue_application catalogue_application_id_seq catalogue_application_records catalogue_application_records_id_seq catalogue_applicationlayer catalogue_applicationlayer_id_seq)
fi

if [[ $dump_data -eq 1 ]]
then
    echo ""
    for table in "${tables[@]}"
    do
        echo "Dump $table data to /tmp/cswmigration/$table"
        PGPASSWORD=$sourcepassword pg_dump -a --column-inserts -F c -n $sourceschema -t $table -h $sourcehost -p $sourceport -d $sourcedatabase -U $sourceuser -f /tmp/cswmigration/$table
    done
    echo "Dump data from source database finsihed"
fi

if [[ $import_data -eq 1 ]]
then
    #clean target database data
    echo ""
    for (( idx=${#tables[@]}-1 ; idx>=0 ; idx-- )) 
    do
        table="${tables[idx]}"
        if [[ "$table" == *_id_seq ]]
        then
            #a sequece table, can't change
            continue
        fi
        echo "Clean $table "
        #normal table, clean the data
        if [[ "$targetuser" == "" ]]
        then
            psql -h $targethost -p $targetport -d $targetdatabase  -c "delete from \"$targetschema\".\"$table\""
        else
            PGPASSWORD=$targetpassword psql -h $targethost -p $targetport -d $targetdatabase  -c "delete from \"$targetschema\".\"$table\""
        fi
    done
    echo "Clean target database finsihed"
    #import to target database
    echo ""
    for table in "${tables[@]}"
    do
        echo "Import $table data from /tmp/cswmigration/$table"
        
        if [[ "$targetuser" == "" ]]
        then
            pg_restore -a -n $targetschema -F c -t $table -h $targethost -p $targetport -d $targetdatabase  /tmp/cswmigration/$table
        else
            PGPASSWORD=$targetpassword pg_restore -a -n $targetschema -F c -t $table -h $targethost -p $targetport -d $targetdatabase -U $targetuser  /tmp/cswmigration/$table
        fi
    done
    echo "Import data to target database finsihed"
fi

if [[ $sync_media -eq 1 ]]
then
    #fetch the static file from source server
    if [[ ! -d $cswhome/media  ]]
    then
        mkdir $cswhome/media
    fi
    if [[ ! -d $cswhome/media/catalogue ]]
    then
        mkdir $cswhome/media/catalogue
    fi
    if [[ ! -d $cswhome/media/catalogue/legends ]]
    then
        mkdir $cswhome/media/catalogue/legends
    fi
    if [[ ! -d $cswhome/media/catalogue/legends/source ]]
    then
        mkdir $cswhome/media/catalogue/legends/source
    fi
    rsync -v -r -u root@aws-oim-001:/var/www/oim-cms.8049/media/catalogue /tmp/cswmigration/media
    #copy and rename the styles name 
    cp -rf /tmp/cswmigration/media/catalogue/styles $cswhome/media/catalogue

    #copy and rename the legend name 
    if [[ "$targetuser" == "" ]]
    then
        psql -h $targethost -p $targetport -d $targetdatabase -c "select legend,id,identifier from catalogue_record where legend is not null and legend !=''" > /tmp/cswmigration/records.txt
    else
        PGPASSWORD=$targetpassword psql -h $targethost -p $targetport -d $targetdatabase -c "select legend,id,identifier from catalogue_record where legend is not null and legend !=''" > /tmp/cswmigration/records.txt
    fi
    while IFS='|' read legend id identifier
    do
        legend="$(echo -e "${legend}" | sed -e 's/^\s\{1,\}//' -e 's/\s\{1,\}$//')"
        if [[ $legend == catalogue* ]]
        then
            IFS='.' read -ra legend_file <<< $legend
            legend_ext=${legend_file[-1]}

            id="$(echo -e "${id}" | sed -e 's/^\s\{1,\}//' -e 's/\s\{1,\}$//')"
            identifier="$(echo -e "${identifier}" | sed -e 's/^\s\{1,\}//' -e 's/\s\{1,\}$//')"
            new_legend_file="$(echo -e "${identifier}" | sed -e 's/\s/_/g' -e 's/\:/_/g'
            new_legend="catalogue/legends/${new_legend_file}.${legend_ext}"
            if [[ ! "$legend" == "$new_legend"  ]]
            then
                echo "$id      $legend              $new_legend"
                #update database
                if [[ "$targetuser" == "" ]]
                then
                    psql -h $targethost -p $targetport -d $targetdatabase -c "update catalogue_record set legend='${new_legend}' where id=${id}" 
                else
                    PGPASSWORD=$targetpassword && psql -h $targethost -p $targetport -d $targetdatabase -c "update catalogue_record set legend='${new_legend}' where id=${id}"
                fi
            fi
            #copy legend file
            cp /tmp/cswmigration/media/${legend} $cswhome/media/${new_legend}
        fi
    done < /tmp/cswmigration/records.txt

    #copy and rename the source legend name 
    if [[ "$targetuser" == "" ]]
    then
        psql -h $targethost -p $targetport -d $targetdatabase -c "select source_legend,id,identifier from catalogue_record where source_legend is not null and source_legend !=''" > /tmp/cswmigration/records.txt
    else
        PGPASSWORD=$targetpassword psql -h $targethost -p $targetport -d $targetdatabase -c "select source_legend,id,identifier from catalogue_record where source_legend is not null and source_legend !=''" > /tmp/cswmigration/records.txt
    fi
    while IFS='|' read legend id identifier
    do
        legend="$(echo -e "${legend}" | sed -e 's/^\s\{1,\}//' -e 's/\s\{1,\}$//')"
        if [[ $legend == catalogue* ]]
        then
            IFS='.' read -ra legend_file <<< $legend
            legend_ext=${legend_file[-1]}

            id="$(echo -e "${id}" | sed -e 's/^\s\{1,\}//' -e 's/\s\{1,\}$//')"
            identifier="$(echo -e "${identifier}" | sed -e 's/^\s\{1,\}//' -e 's/\s\{1,\}$//')"
            new_legend_file="$(echo -e "${identifier}" | sed -e 's/\s/_/g' -e 's/\:/_/g'  | sed -e 's/_\{2,\}/_/g')"
            new_legend="catalogue/legends/source/${new_legend_file}.${legend_ext}"
            if [[ ! "$legend" == "$new_legend"  ]]
            then
                echo "$id      $legend              $new_legend"
                #update database
                if [[ "$targetuser" == "" ]]
                then
                    psql -h $targethost -p $targetport -d $targetdatabase -c "update catalogue_record set source_legend='${new_legend}' where id=${id}" 
                else
                    PGPASSWORD=$targetpassword && psql -h $targethost -p $targetport -d $targetdatabase -c "update catalogue_record set source_legend='${new_legend}' where id=${id}"
                fi
            fi
            #copy source legend file
            cp /tmp/cswmigration/media/${legend} $cswhome/media/${new_legend}
        fi
    done < /tmp/cswmigration/records.txt

fi


if [[ $clear_data -eq 1 ]]
then
    if [[ -d /tmp/cswmigration ]]
    then
        rm -rf /tmp/cswmigration
        echo "Clear the dumped data"
    fi
fi

